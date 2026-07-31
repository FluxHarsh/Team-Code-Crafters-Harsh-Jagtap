"""
Orchestrates the post-approval coach chat panel (architecture doc
Section 5.7): persist the user's turn, classify it, dispatch, persist
the agent's reply, and return both.

Workstream A3/A4 change: a "replan"/"reprioritize" message from chat no
longer mutates the roadmap directly. The Planner reopens its own
draft/review/approve loop -- chat's job is to *suggest* that redirect
(or, for reprioritize, to write the pending planner_suggestions row
via app.services.risk_service.propose_reprioritization) and point the
user at the Planner sidebar, never to call replan_roadmap itself.
"""

from __future__ import annotations

import logging

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.supervisor import (
    CATEGORY_TO_ANSWERED_BY,
    classify_chat_category,
    classify_coach_message,
)
from app.agents.nodes.team_assistant import run_team_assistant
from app.errors import ConflictError, NotFoundError
from app.models.project import Project
from app.repositories import chat_messages as chat_messages_repo
from app.services.risk_service import propose_reprioritization

logger = logging.getLogger(__name__)

PHASE = "coaching"


async def handle_coach_message(
    session: AsyncSession,
    driver: AsyncDriver,
    project: Project,
    message: str,
    *,
    speaker_name: str | None = None,
    chat_scope: str = "group",
) -> tuple[str, str]:
    """Returns (reply, answered_by)."""
    await chat_messages_repo.add_message(
        session,
        project_id=project.id,
        phase=PHASE,
        role="user",
        content=message,
        speaker_name=speaker_name,
        chat_scope=chat_scope,
        mentions_ai=True,
    )

    unresolved_risks = [r for r in (project.risks or []) if not r.get("resolved")]
    action, risk_id = classify_coach_message(message, unresolved_risks)

    if action == "replan":
        reply, answered_by = _handle_replan_redirect(message)
    elif action == "reprioritize":
        reply, answered_by = await _handle_reprioritize_suggest(session, driver, project, risk_id)
    else:
        category = classify_chat_category(message)
        answered_by = CATEGORY_TO_ANSWERED_BY.get(category, "team_assistant")
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
        session,
        project_id=project.id,
        phase=PHASE,
        role="agent",
        content=reply,
        agent_node=answered_by,
        chat_scope=chat_scope,
    )
    return reply, answered_by


def _handle_replan_redirect(message: str) -> tuple[str, str]:
    """A3: chat never calls replan_roadmap directly anymore -- it
    points the team at the Planner sidebar, where the real
    draft/edit/approve loop lives (app/routers/planner_suggestions.py,
    app/routers/planning.py)."""
    return (
        "Looks like you want to change the plan. I won't rewrite the roadmap from "
        "chat directly -- open the Planner panel to review and approve a re-plan there.",
        "planner",
    )


async def _handle_reprioritize_suggest(
    session: AsyncSession, driver: AsyncDriver, project: Project, risk_id: str | None
) -> tuple[str, str]:
    if risk_id is None:
        return (
            "Which risk do you mean? There's more than one open right now -- "
            "mention its id (from the risk feed) and I'll draft a fix suggestion for it.",
            "team_assistant",
        )
    try:
        result = await propose_reprioritization(session, driver, project, risk_id, reason="coach chat")
        reply = (
            f"I've drafted a suggestion ({result.decision}) for risk {risk_id} -- "
            f"{result.rationale}. Open the Planner sidebar to accept or dismiss it."
        )
        return reply, "risk_watcher"
    except ConflictError:
        return "A re-plan is already running for this project -- give it a moment and ask again.", "risk_watcher"
    except NotFoundError:
        return f"I couldn't find a risk with id {risk_id!r} -- check the risk feed for the current id.", "risk_watcher"
