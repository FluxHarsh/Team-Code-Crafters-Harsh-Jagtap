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
from app.errors import ConflictError, NotFoundError
from app.models.planner_suggestion import PlannerSuggestion
from app.models.project import Project
from app.repositories import graph as graph_repo
from app.repositories import planner_suggestions as planner_suggestions_repo
from app.repositories import projects as projects_repo
from app.services.roadmap_service import replan_roadmap
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)

# How many hops the "what does fixing this unblock?" traversal walks --
# matches the *1..3 bound in architecture doc Section 3.3's example.
TRAVERSAL_MAX_HOPS = 3


@dataclass
class PlannerSuggestionResult:
    id: str
    status: str
    decision: str | None
    rationale: str


@dataclass
class AcceptResult:
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


async def propose_reprioritization(
    session: AsyncSession, driver: AsyncDriver, project: Project, risk_id: str, *, reason: str = "manual_request"
) -> PlannerSuggestionResult:
    """Workstream A3 replacement for the old auto-apply reprioritize_risk:
    find the risk, traverse Neo4j for what fixing it would unblock, ask
    the Reprioritizer to decide -- then, instead of immediately calling
    replan_roadmap, write a pending planner_suggestions row and stop.
    Nothing about the roadmap changes until a human calls
    accept_suggestion."""
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

    suggestion = await planner_suggestions_repo.create_suggestion(
        session,
        project_id=project.id,
        source="risk_reprioritization",
        risk_id=risk_id,
        decision=decision.decision,
        rationale=decision.rationale,
        context={
            "risk": risk,
            "downstream_milestones": downstream_milestones,
            "suggested_fix": risk.get("suggested_fix"),
        },
    )
    await broadcast(
        project.id,
        "planner_suggestion_created",
        {"id": str(suggestion.id), "risk_id": risk_id, "decision": decision.decision, "rationale": decision.rationale},
    )

    logger.info(
        "risk_reprioritization_proposed",
        extra={"project_id": str(project.id), "risk_id": risk_id, "suggestion_id": str(suggestion.id)},
    )
    return PlannerSuggestionResult(
        id=str(suggestion.id), status=suggestion.status, decision=decision.decision, rationale=decision.rationale
    )


async def accept_suggestion(
    session: AsyncSession, driver: AsyncDriver, project: Project, suggestion_id
) -> AcceptResult:
    """The only path that turns a pending planner_suggestions row into
    an actual roadmap change -- runs replan_roadmap (which itself writes
    the planner_history row) and, if the suggestion came from a risk,
    marks that risk resolved."""
    suggestion = await planner_suggestions_repo.get_suggestion(session, suggestion_id)
    if suggestion is None or suggestion.project_id != project.id:
        raise NotFoundError(f"Suggestion {suggestion_id} not found")
    if suggestion.status != "pending":
        raise ConflictError(f"Suggestion already {suggestion.status}")

    replan_reason = (
        f"accepted planner suggestion {suggestion.id} "
        f"(risk {suggestion.risk_id}): {suggestion.decision} -- {suggestion.rationale}"
    )
    await replan_roadmap(session, driver, project, reason=replan_reason)

    if suggestion.risk_id:
        await resolve_risk(
            session, driver, project, suggestion.risk_id,
            resolution_note=f"Reprioritizer: {suggestion.decision} -- {suggestion.rationale}",
        )

    await planner_suggestions_repo.set_status(session, suggestion.id, "accepted")
    await broadcast(project.id, "planner_suggestion_accepted", {"id": str(suggestion.id)})

    logger.info(
        "planner_suggestion_accepted",
        extra={"project_id": str(project.id), "suggestion_id": str(suggestion.id)},
    )
    return AcceptResult(decision=suggestion.decision or "", rationale=suggestion.rationale, roadmap_replanned=True)


async def dismiss_suggestion(session: AsyncSession, project: Project, suggestion_id) -> PlannerSuggestion:
    suggestion = await planner_suggestions_repo.get_suggestion(session, suggestion_id)
    if suggestion is None or suggestion.project_id != project.id:
        raise NotFoundError(f"Suggestion {suggestion_id} not found")
    if suggestion.status != "pending":
        raise ConflictError(f"Suggestion already {suggestion.status}")

    updated = await planner_suggestions_repo.set_status(session, suggestion.id, "dismissed")
    await broadcast(project.id, "planner_suggestion_dismissed", {"id": str(suggestion.id)})
    return updated
