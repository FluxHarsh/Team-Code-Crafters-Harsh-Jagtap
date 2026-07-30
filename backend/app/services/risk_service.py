"""
Orchestrates the two Phase 6 nodes (Implementation Plan Phase 6):
run_risk_watcher_for_project (rule-based detection + persistence + the
Risk/AFFECTS Neo4j sync) and reprioritize_risk (Neo4j downstream
traversal -> Reprioritizer decision -> Phase 4's replan_roadmap ->
resolve the risk). Routes call this instead of touching the
nodes/repositories directly, same split as planning_service.py /
roadmap_service.py / github_service.py.

run_risk_watcher_for_project is called from two places:
  - app/services/github_service.py's poll hand-off (was a stub through
    Phase 5, wired for real here).
  - app/routers/risks.py's POST .../progress route.
Both call this exact function so there's one code path that ever adds
to projects.risks, same "one predictable code path" goal as the rest
of the Monitoring loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.reprioritizer import run_reprioritizer
from app.agents.nodes.risk_watcher import run_risk_watcher
from app.errors import NotFoundError
from app.models.project import Project
from app.repositories import graph as graph_repo
from app.repositories import projects as projects_repo
from app.services.roadmap_service import replan_roadmap
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)

# How many hops the "what does fixing this unblock?" traversal walks --
# matches the *1..3 bound in architecture doc Section 3.3's example.
TRAVERSAL_MAX_HOPS = 3


@dataclass
class ReprioritizeResult:
    decision: str
    rationale: str
    roadmap_replanned: bool


async def run_risk_watcher_for_project(
    session: AsyncSession, driver: AsyncDriver, project: Project, *, trigger: str
) -> list[dict]:
    """Runs the Risk Watcher's rules, appends any newly-detected risks
    to projects.risks, and creates the matching Risk/AFFECTS nodes in
    Neo4j. Returns just the newly-added risks (empty list if nothing
    new was detected) -- callers that care about "did anything actually
    get flagged" vs. "did the watcher run" can tell the difference."""
    existing_risks = list(project.risks or [])
    new_risks = await run_risk_watcher(
        session,
        project_id=project.id,
        roadmap=project.roadmap or [],
        github_state=project.github_state or {},
        progress_log=project.progress_log or [],
        existing_risks=existing_risks,
        trigger=trigger,
    )

    if new_risks:
        await projects_repo.update_project(session, project.id, risks=existing_risks + new_risks)
        for risk in new_risks:
            await graph_repo.create_risk_node(
                driver, risk["id"], severity=risk["severity"], task_id=risk.get("task_id")
            )
            await broadcast(project.id, "risk_flagged", {"risk": risk})
        logger.info(
            "risk_watcher_flagged_new_risks",
            extra={"project_id": str(project.id), "count": len(new_risks)},
        )

    return new_risks


async def resolve_risk(
    session: AsyncSession, driver: AsyncDriver, project: Project, risk_id: str, *, resolution_note: str | None = None
) -> dict:
    """Marks one risk resolved in Postgres and Neo4j and broadcasts
    risk_resolved (Section 6, { risk_id }). Shared by the manual
    POST .../risks/{id}/resolve route and reprioritize_risk below (Section
    5.5's "roadmap_replanned: true" case) so there's exactly one code
    path that ever flips resolved=True, same reasoning as every other
    shared service function in this codebase."""
    risks = list(project.risks or [])
    index = next((i for i, r in enumerate(risks) if r.get("id") == risk_id), None)
    if index is None:
        raise NotFoundError(f"Risk {risk_id} not found")

    risk = dict(risks[index])
    risk["resolved"] = True
    if resolution_note is not None:
        risk["resolution_note"] = resolution_note
    risks[index] = risk

    await projects_repo.update_project(session, project.id, risks=risks)
    await graph_repo.mark_risk_resolved(driver, risk_id)
    await broadcast(project.id, "risk_resolved", {"risk_id": risk_id})

    return risk


async def reprioritize_risk(
    session: AsyncSession, driver: AsyncDriver, project: Project, risk_id: str, *, reason: str = "manual_request"
) -> ReprioritizeResult:
    """Section 5.5's full flow: find the risk, traverse Neo4j for what
    fixing it would unblock, ask the Reprioritizer to decide, then --
    regardless of which decision came back -- actually apply it by
    running Phase 4's replan_roadmap (the Planner sees the risk's
    suggested_fix and the Reprioritizer's decision/rationale folded into
    the replan reason, so the rebuilt roadmap reflects the call made
    here) and mark the risk resolved."""
    risks = list(project.risks or [])
    risk = next((r for r in risks if r.get("id") == risk_id), None)
    if risk is None:
        raise NotFoundError(f"Risk {risk_id} not found")

    task_id = risk.get("task_id")
    task = next((t for t in (project.roadmap or []) if t.get("id") == task_id), None) if task_id else None

    downstream_milestones = []
    if task_id:
        downstream_milestones = await graph_repo.traverse_downstream_milestones(
            driver, task_id, max_hops=TRAVERSAL_MAX_HOPS
        )

    decision = await run_reprioritizer(
        session,
        project_id=project.id,
        risk=risk,
        task=task,
        downstream_milestones=downstream_milestones,
        scope=project.scope or {},
        hours_remaining=float(project.hours_remaining) if project.hours_remaining is not None else None,
        trigger=reason,
    )

    replan_reason = (
        f"reprioritize risk {risk_id} ({risk.get('risk')}): "
        f"Reprioritizer decided '{decision.decision}' -- {decision.rationale}. "
        f"Suggested fix: {risk.get('suggested_fix')}"
    )
    await replan_roadmap(session, driver, project, reason=replan_reason)
    await resolve_risk(
        session, driver, project, risk_id, resolution_note=f"Reprioritizer: {decision.decision} -- {decision.rationale}"
    )

    logger.info(
        "risk_reprioritized",
        extra={"project_id": str(project.id), "risk_id": risk_id, "decision": decision.decision},
    )
    return ReprioritizeResult(decision=decision.decision, rationale=decision.rationale, roadmap_replanned=True)
