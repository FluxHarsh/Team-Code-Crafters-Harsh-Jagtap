"""
Typed Neo4j writes/reads for the dependency graph (architecture doc
Section 3.3): Project/Milestone nodes with BELONGS_TO/BLOCKED_BY
(Phase 4), CommitFile/MAPS_TO (Phase 5), and Risk/AFFECTS plus the
downstream-impact traversal (Phase 6).

Called from app/services/roadmap_service.py after every roadmap write,
app/services/github_service.py after every poll, and
app/services/risk_service.py whenever a risk is created/resolved — so
the graph never drifts from the Postgres state that's supposed to be
its source of truth. traverse_downstream_milestones is what the
Reprioritizer (Phase 6) runs before deciding drop/extend/reassign.

Tasks carry an optional "depends_on": [task_id, ...] field (a natural
extension of the JSONB roadmap shape in Section 3.1 — the doc calls
out that these fields evolve without a migration). The Planner prompt
(app/agents/prompts.py) now asks for it explicitly so there's real
dependency data to sync instead of an always-empty graph.
"""

from __future__ import annotations

import uuid

from neo4j import AsyncDriver


async def sync_roadmap(driver: AsyncDriver, project_id: uuid.UUID, roadmap: list[dict]) -> None:
    """Upserts one Milestone node per task (id, name, status), a
    BELONGS_TO edge to the Project node, and BLOCKED_BY edges from each
    task's own "depends_on" list. Idempotent and safe to call after
    every roadmap write: stale BLOCKED_BY edges (a dependency that was
    removed by a later edit/replan) are deleted, and tasks no longer
    present in the roadmap are removed entirely so the graph never
    accumulates orphaned milestones from an earlier draft."""
    pid = str(project_id)
    tasks = [t for t in roadmap if isinstance(t, dict) and t.get("id")]
    current_ids = [t["id"] for t in tasks]

    async with driver.session() as session:
        await session.run("MERGE (:Project {id: $pid})", pid=pid)

        # Remove milestones that no longer exist in this roadmap (e.g. a
        # task dropped by a replan) before upserting the current set, so
        # a stale Milestone can't keep dangling BLOCKED_BY edges around.
        await session.run(
            """
            MATCH (m:Milestone)-[:BELONGS_TO]->(:Project {id: $pid})
            WHERE NOT m.id IN $current_ids
            DETACH DELETE m
            """,
            pid=pid,
            current_ids=current_ids,
        )

        for task in tasks:
            await session.run(
                """
                MERGE (m:Milestone {id: $id})
                SET m.name = $name, m.status = $status
                WITH m
                MATCH (p:Project {id: $pid})
                MERGE (m)-[:BELONGS_TO]->(p)
                """,
                id=task["id"],
                name=task.get("task", ""),
                status=task.get("status", "todo"),
                pid=pid,
            )

        for task in tasks:
            depends_on = [d for d in (task.get("depends_on") or []) if d in current_ids]
            await session.run(
                "MATCH (m:Milestone {id: $id})-[r:BLOCKED_BY]->() DELETE r",
                id=task["id"],
            )
            for blocker_id in depends_on:
                await session.run(
                    """
                    MATCH (m:Milestone {id: $id}), (b:Milestone {id: $blocker_id})
                    MERGE (m)-[:BLOCKED_BY]->(b)
                    """,
                    id=task["id"],
                    blocker_id=blocker_id,
                )


async def upsert_milestone_status(driver: AsyncDriver, task_id: str, status: str) -> None:
    """Lighter-weight single-task update for the Kanban PATCH route —
    avoids re-running the full roadmap sync (and its edge diffing) for
    a status-only drag-and-drop move."""
    async with driver.session() as session:
        await session.run(
            "MATCH (m:Milestone {id: $id}) SET m.status = $status",
            id=task_id,
            status=status,
        )


async def sync_commit_files(driver: AsyncDriver, matched_commits: list) -> None:
    """Upserts one CommitFile node per changed file path in a matched
    commit and a MAPS_TO edge to the Milestone it was matched against
    (Section 3.3), so the file-to-milestone mapping is queryable
    ("what files touch this milestone?"). Skips commits the keyword/
    path matcher couldn't tie to any task -- an unmatched CommitFile
    with no MAPS_TO edge would just be graph noise, not useful signal
    for the Reprioritizer's traversal (Phase 6).

    `matched_commits` is a list of objects/dicts with `.matched_task`
    (or `["matched_task"]`) and `.files` (or `["files"]") -- accepts
    either app.agents.nodes.github_watcher.MatchedCommit instances or
    plain dicts so callers/tests don't need to import that dataclass.
    """
    async with driver.session() as session:
        for commit in matched_commits:
            matched_task = getattr(commit, "matched_task", None) if not isinstance(commit, dict) else commit.get("matched_task")
            files = getattr(commit, "files", None) if not isinstance(commit, dict) else commit.get("files")
            if not matched_task or not files:
                continue
            for path in files:
                await session.run(
                    """
                    MERGE (cf:CommitFile {path: $path})
                    WITH cf
                    MATCH (m:Milestone {id: $task_id})
                    MERGE (cf)-[:MAPS_TO]->(m)
                    """,
                    path=path,
                    task_id=matched_task,
                )


async def create_risk_node(driver: AsyncDriver, risk_id: str, *, severity: str, task_id: str | None) -> None:
    """MERGEs a Risk node and, if the risk is tied to a specific
    roadmap task, an AFFECTS edge to that task's Milestone (Section
    3.3). Risks with no task_id (e.g. a general/manual risk not tied
    to one task) still get a node -- just no edge -- so they don't
    silently vanish from the graph view."""
    async with driver.session() as session:
        await session.run(
            "MERGE (r:Risk {id: $id}) SET r.severity = $severity, r.resolved = false",
            id=risk_id,
            severity=severity,
        )
        if task_id:
            await session.run(
                """
                MATCH (r:Risk {id: $id}), (m:Milestone {id: $task_id})
                MERGE (r)-[:AFFECTS]->(m)
                """,
                id=risk_id,
                task_id=task_id,
            )


async def mark_risk_resolved(driver: AsyncDriver, risk_id: str) -> None:
    """Called from POST .../risks/{risk_id}/resolve (manual) and from
    the Reprioritizer after a successful replan clears the underlying
    task (Section 5.5's "roadmap_replanned: true" case) -- same node,
    same property, whichever path resolves it."""
    async with driver.session() as session:
        await session.run("MATCH (r:Risk {id: $id}) SET r.resolved = true", id=risk_id)


async def traverse_downstream_milestones(
    driver: AsyncDriver, milestone_id: str, *, max_hops: int = 3
) -> list[dict]:
    """The exact traversal from Section 3.3: "if I fix this milestone,
    these downstream milestones become unblockable." BLOCKED_BY points
    from a task to the thing blocking it (task-[:BLOCKED_BY]->blocker),
    so walking the edge *backwards* from `milestone_id` finds every
    milestone that (transitively, up to max_hops) depends on it.
    DISTINCT because a variable-length path can reach the same
    downstream milestone via more than one route."""
    async with driver.session() as session:
        result = await session.run(
            f"""
            MATCH (m:Milestone {{id: $milestone_id}})<-[:BLOCKED_BY*1..{int(max_hops)}]-(downstream)
            RETURN DISTINCT downstream.id AS id, downstream.name AS name
            """,
            milestone_id=milestone_id,
        )
        records = await result.data()
    return [{"id": r["id"], "name": r["name"]} for r in records]
