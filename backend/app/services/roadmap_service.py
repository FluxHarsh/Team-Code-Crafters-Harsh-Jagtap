"""
Orchestrates the roadmap/Kanban read-write paths (Implementation Plan
Phase 4): the manual + Monitoring-loop replan, and the Kanban PATCH.
Routes call this instead of touching app.agents/app.repositories
directly, same split as app/services/planning_service.py in Phase 3.

Both entrypoints keep the Neo4j dependency graph (Section 3.3) in sync
with whatever just got written to Postgres, since the Reprioritizer's
traversal (Phase 6) reads the graph, not the JSONB column, to answer
"what does fixing this unblock?".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_replan_turn
from app.errors import ConflictError, NotFoundError
from app.models.project import Project
from app.repositories import critique_history as critique_history_repo
from app.repositories import graph as graph_repo
from app.repositories import projects as projects_repo
from app.repositories.locks import try_acquire_replan_lock
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)

MAX_PRIOR_CRITIQUES = 20

# A task landing here means "no one's confirmed it can proceed" --
# good enough for an immediate Kanban-facing flag while Phase 6's Risk
# Watcher does the real github_state/ETA-driven detection.
BLOCKED_TASK_STATUS = "blocked"

# Internal task status vocabulary (todo/in_progress/blocked/done, as
# written by the Planner -- see app/agents/prompts.py -- and stored in
# projects.roadmap) mapped to the board's column vocabulary
# (queued/building/blocked/shipped). Anything unrecognized falls back to
# "queued" in build_roadmap_board rather than raising, so one malformed
# task can't break the whole board response.
_STATUS_TO_COLUMN = {
    "todo": "queued",
    "in_progress": "building",
    "blocked": "blocked",
    "done": "shipped",
}


@dataclass
class ReplanResult:
    status: str
    roadmap: list
    next_action: str | None


@dataclass
class TaskPatchResult:
    task: dict
    risk_flagged: bool


@dataclass
class BoardResult:
    summary: dict
    nodes: list[dict]
    edges: list[dict]


async def replan_roadmap(
    session: AsyncSession, driver: AsyncDriver, project: Project, *, reason: str
) -> ReplanResult:
    """Rebuilds the roadmap from current scope + hours_remaining via the
    Planner node (architecture doc Section 5.2). Shared by the manual
    'replan' route and, later, the automatic Monitoring loop (Phase 6/10)
    -- both call this same function so there's exactly one code path
    that mutates the roadmap outside the planning chat."""
    if not await try_acquire_replan_lock(session, project.id):
        raise ConflictError("A re-plan is already in flight for this project")

    prior_critiques = await critique_history_repo.list_critiques_for_project(session, project.id)
    prior_critique_texts = [c.critique_text for c in prior_critiques[-MAX_PRIOR_CRITIQUES:]]

    result_state = await run_replan_turn(
        session,
        project_id=project.id,
        project_idea=project.project_idea or {},
        scope=project.scope or {},
        roadmap=project.roadmap or [],
        hours_remaining=float(project.hours_remaining) if project.hours_remaining is not None else None,
        prior_critique_texts=prior_critique_texts,
        reason=reason,
    )

    new_scope = result_state["draft_scope"]
    new_roadmap = result_state["draft_roadmap"]

    updated = await projects_repo.update_project(
        session,
        project.id,
        scope=new_scope,
        roadmap=new_roadmap,
        next_action="supervisor",
    )

    await graph_repo.sync_roadmap(driver, project.id, new_roadmap)

    logger.info("roadmap_replanned", extra={"project_id": str(project.id), "reason": reason})
    return ReplanResult(status=updated.status, roadmap=new_roadmap, next_action=updated.next_action)


async def patch_task(
    session: AsyncSession,
    driver: AsyncDriver,
    project_id,
    task_id: str,
    *,
    status: str | None,
    owner: str | None,
    eta: str | None,
    note: str | None,
) -> TaskPatchResult:
    """Read-modify-write a single task inside projects.roadmap under a
    row-level lock (SELECT ... FOR UPDATE), so a drag-and-drop from one
    tab can't silently clobber a concurrent edit from another (Phase 4:
    'read-modify-write with row-level lock to avoid clobbering
    concurrent writes'). The lock is held for the rest of this
    transaction and released automatically when the request's session
    commits (app.dependencies.get_db)."""
    project = await projects_repo.get_project_for_update(session, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")

    roadmap = list(project.roadmap or [])
    index = next((i for i, t in enumerate(roadmap) if t.get("id") == task_id), None)
    if index is None:
        raise NotFoundError(f"Task {task_id} not found")

    task = dict(roadmap[index])
    old_status = task.get("status")
    if status is not None:
        task["status"] = status
    if owner is not None:
        task["owner"] = owner
    if eta is not None:
        task["eta"] = eta
    if note is not None:
        task["note"] = note
    roadmap[index] = task

    await projects_repo.update_project(session, project.id, roadmap=roadmap)
    await graph_repo.upsert_milestone_status(driver, task_id, task.get("status", "todo"))

    # Column-change-specific event -- only when status actually moved,
    # not on an owner/eta/note-only edit (those are covered by
    # update_project's generic state_updated(path="roadmap") above).
    if status is not None and status != old_status:
        await broadcast(
            project.id, "task_moved", {"task_id": task_id, "from": old_status, "to": status}
        )

    risk_flagged = task.get("status") == BLOCKED_TASK_STATUS
    logger.info(
        "roadmap_task_patched",
        extra={"project_id": str(project.id), "task_id": task_id, "risk_flagged": risk_flagged},
    )
    return TaskPatchResult(task=task, risk_flagged=risk_flagged)


def build_roadmap_board(project: Project) -> BoardResult:
    """Reshapes projects.roadmap (+ github_state's commit count) into
    the Queued/Building/Blocked/Shipped board view -- column-labeled
    nodes, per-column counts, overall percent-complete, and an explicit
    `edges` list built from each task's own `depends_on`.

    Pure computation over an already-loaded project: no DB or Neo4j
    calls here. The Neo4j BLOCKED_BY mirror (app/repositories/graph.py)
    exists for the Reprioritizer's downstream-impact traversal, not for
    this -- Postgres' `depends_on` is the same source data and is
    already in memory once the project's loaded, so reading it back out
    of Neo4j here would just be a slower, redundant read of the exact
    same thing.
    """
    tasks = [t for t in (project.roadmap or []) if isinstance(t, dict) and t.get("id")]
    valid_ids = {t["id"] for t in tasks}

    nodes = []
    counts = {"queued": 0, "building": 0, "blocked": 0, "shipped": 0}
    edges = []

    for task in tasks:
        column = _STATUS_TO_COLUMN.get(task.get("status"), "queued")
        counts[column] += 1
        nodes.append(
            {
                "id": task["id"],
                "task": task.get("task", ""),
                "column": column,
                "owner": task.get("owner") or "",
                "eta": task.get("eta") or "",
            }
        )
        for blocker_id in task.get("depends_on") or []:
            if blocker_id in valid_ids:
                edges.append({"from": blocker_id, "to": task["id"]})

    total = len(tasks)
    shipped = counts["shipped"]
    commit_count = len((project.github_state or {}).get("commits", []))

    summary = {
        "percent_complete": round(shipped / total * 100) if total else 0,
        "total_tasks": total,
        "shipped_count": shipped,
        "commit_count": commit_count,
        "counts": counts,
    }
    return BoardResult(summary=summary, nodes=nodes, edges=edges)
