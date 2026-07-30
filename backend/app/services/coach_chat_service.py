"""
Orchestrates the post-approval coach chat panel (Implementation Plan
Phase 8, architecture doc Section 5.7): persist the user's turn,
classify it (app.agents.nodes.supervisor.classify_coach_message),
dispatch to whichever of Phase 4's replan_roadmap, Phase 6's
reprioritize_risk, or Phase 8's own Team Assistant actually handles it,
persist the agent's reply, and return both. Routes call this instead
of touching app.agents/app.services.{roadmap,risk}_service directly,
same split as every other phase's service module.

This reuses Phase 4/6's real service functions rather than
reimplementing "trigger a replan"/"reprioritize a risk" -- typing
"re-plan the roadmap" into the coach chat panel and calling
POST .../roadmap/replan are meant to be the same action taken two
different ways, not two different code paths that could drift.
"""

from __future__ import annotations

import logging

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.supervisor import classify_coach_message, guess_answered_by
from app.agents.nodes.team_assistant import run_team_assistant
from app.errors import ConflictError, NotFoundError
from app.models.project import Project
from app.repositories import chat_messages as chat_messages_repo
from app.services.risk_service import reprioritize_risk
from app.services.roadmap_service import replan_roadmap

logger = logging.getLogger(__name__)

PHASE = "coaching"


async def handle_coach_message(
    session: AsyncSession, driver: AsyncDriver, project: Project, message: str, *, speaker_name: str | None = None
) -> tuple[str, str]:
    """Returns (reply, answered_by)."""
    await chat_messages_repo.add_message(
        session, project_id=project.id, phase=PHASE, role="user", content=message, speaker_name=speaker_name
    )

    unresolved_risks = [r for r in (project.risks or []) if not r.get("resolved")]
    action, risk_id = classify_coach_message(message, unresolved_risks)

    if action == "replan":
        reply, answered_by = await _handle_replan(session, driver, project, message)
    elif action == "reprioritize":
        reply, answered_by = await _handle_reprioritize(session, driver, project, risk_id)
    else:
        answered_by = guess_answered_by(message)
        reply = await run_team_assistant(
            session,
            project_id=project.id,
            message=message,
            project_idea=project.project_idea or {},
            scope=project.scope or {},
            roadmap=project.roadmap or [],
            risks=project.risks or [],
            github_state=project.github_state or {},
            pitch_outline=project.pitch_outline,
            trigger="user_action",
        )

    await chat_messages_repo.add_message(
        session, project_id=project.id, phase=PHASE, role="agent", content=reply, agent_node=answered_by
    )
    return reply, answered_by


async def _handle_replan(session: AsyncSession, driver: AsyncDriver, project: Project, message: str) -> tuple[str, str]:
    try:
        result = await replan_roadmap(session, driver, project, reason=f"coach chat: {message}")
        reply = f"Replanned the roadmap -- {len(result.roadmap)} tasks in the plan now."
    except ConflictError:
        reply = "A re-plan is already running for this project -- give it a moment and ask again."
    return reply, "planner"


async def _handle_reprioritize(
    session: AsyncSession, driver: AsyncDriver, project: Project, risk_id: str | None
) -> tuple[str, str]:
    if risk_id is None:
        return (
            "Which risk do you mean? There's more than one open right now -- "
            "mention its id (from the risk feed) and I'll fix that one.",
            "team_assistant",
        )
    try:
        result = await reprioritize_risk(session, driver, project, risk_id, reason="coach chat")
        reply = f"Decided to {result.decision} -- {result.rationale}"
        return reply, "reprioritizer"
    except ConflictError:
        return "A re-plan is already running for this project -- give it a moment and ask again.", "reprioritizer"
    except NotFoundError:
        return f"I couldn't find a risk with id {risk_id!r} -- check the risk feed for the current id.", "reprioritizer"
