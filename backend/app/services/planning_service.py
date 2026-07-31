"""
Orchestrates the planning chat turn (Implementation Plan Phase 3):
persist the user's turn, invoke Scope Critic then Planner via the
LangGraph skeleton, persist the agent's reply, and write the resulting
draft scope/roadmap back onto the projects row. Routes call this
instead of touching app.agents or app.repositories directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_planning_turn
from app.errors import UnprocessableEntityError
from app.models.project import Project

from app.repositories import chat_messages as chat_messages_repo
from app.repositories import critique_history as critique_history_repo
from app.repositories import projects as projects_repo
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)

# How many prior critiques to feed back in as context -- enough for the
# Planner to avoid repeating itself without the prompt growing unbounded
# over a long planning conversation.
MAX_PRIOR_CRITIQUES = 20


@dataclass
class PlanChatResult:
    reply: str
    draft_scope: dict
    draft_roadmap: list


async def handle_plan_chat(
    session: AsyncSession, project: Project, message: str, *, speaker_name: str | None = None
) -> PlanChatResult:
    await chat_messages_repo.add_message(
        session,
        project_id=project.id,
        phase="planning",
        role="user",
        content=message,
        speaker_name=speaker_name,
    )

    prior_critiques = await critique_history_repo.list_critiques_for_project(session, project.id)
    prior_critique_texts = [c.critique_text for c in prior_critiques[-MAX_PRIOR_CRITIQUES:]]

    result_state = await run_planning_turn(
        session,
        project_id=project.id,
        project_idea=project.project_idea or {},
        scope=project.scope or {},
        roadmap=project.roadmap or [],
        hours_remaining=float(project.hours_remaining) if project.hours_remaining is not None else None,
        prior_critique_texts=prior_critique_texts,
        user_message=message,
    )

    reply = result_state["reply"]
    draft_scope = result_state["draft_scope"]
    draft_roadmap = result_state["draft_roadmap"]

    # Validate planner output before saving
    has_scope = isinstance(draft_scope, dict) and (
        bool(draft_scope.get("mvp_features"))
        or bool(draft_scope.get("cut_features"))
        or bool(draft_scope.get("assumptions"))
    )
    has_roadmap = isinstance(draft_roadmap, list) and len(draft_roadmap) > 0

    if not has_scope and not has_roadmap:
        raise UnprocessableEntityError(
            "Planner agent failed to generate a valid plan draft. Please retry."
        )

    # Validate roadmap tasks schema
    valid_statuses = {"todo", "in_progress", "blocked", "done"}
    for task in draft_roadmap:
        if not isinstance(task, dict) or "id" not in task or "task" not in task:
            raise UnprocessableEntityError("Planner output contains malformed roadmap tasks.")
        if task.get("status") not in valid_statuses:
            task["status"] = "todo"

    await chat_messages_repo.add_message(
        session,
        project_id=project.id,
        phase="planning",
        role="agent",
        content=reply,
        agent_node="planner",
    )

    await projects_repo.update_project(
        session,
        project.id,
        scope=draft_scope,
        roadmap=draft_roadmap,
        next_action="planner",
    )

    # The combined { draft_scope, draft_roadmap } shape Section 6
    # documents for this event -- update_project already fired two
    # separate generic state_updated events (path="scope",
    # path="roadmap"); this is the richer, chat-screen-specific one.
    await broadcast(
        project.id, "plan_draft_updated", {"draft_scope": draft_scope, "draft_roadmap": draft_roadmap}
    )

    logger.info("plan_chat_handled", extra={"project_id": str(project.id)})
    return PlanChatResult(reply=reply, draft_scope=draft_scope, draft_roadmap=draft_roadmap)
