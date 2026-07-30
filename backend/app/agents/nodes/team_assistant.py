"""
Team Assistant node -- architecture doc Section 5.7. Answers a
question-type coach-chat message grounded in the project's current
state (project_idea/scope/roadmap/risks/github_state/pitch_outline).
The one Phase 8 node that calls the LLM -- classification itself
(app.agents.nodes.supervisor.classify_coach_message) is rule-based;
this is where free-text understanding actually earns its keep.

Plain-text reply, not JSON -- unlike the other LLM nodes in this
codebase, there's no structured multi-field output to parse here, just
the answer a person reads directly in the chat panel. That also means
there's no "malformed JSON" failure mode to fall back from -- only a
genuine call failure, handled with a plain apologetic reply rather than
inventing an answer the state doesn't actually support.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import get_chat_model
from app.agents.prompts import TEAM_ASSISTANT_SYSTEM
from app.repositories import agent_run_log as agent_run_log_repo

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "I couldn't pull that up right now -- try asking again in a moment, "
    "or check the roadmap/risks panels directly."
)


async def run_team_assistant(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    message: str,
    project_idea: dict,
    scope: dict,
    roadmap: list[dict],
    risks: list[dict],
    github_state: dict,
    pitch_outline: dict | None,
    trigger: str,
) -> str:
    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="team_assistant",
        trigger=trigger,
        input_snapshot={"message": message},
    )

    try:
        model = get_chat_model(temperature=0.3)
        response = await model.ainvoke(
            [
                ("system", TEAM_ASSISTANT_SYSTEM),
                (
                    "human",
                    f"Project idea: {project_idea}\n\n"
                    f"Current scope: {scope}\n\n"
                    f"Roadmap: {roadmap}\n\n"
                    f"Risks: {risks}\n\n"
                    f"GitHub state: {github_state}\n\n"
                    f"Pitch outline: {pitch_outline}\n\n"
                    f"Team's question: {message}",
                ),
            ]
        )
        reply = response.content if isinstance(response.content, str) else str(response.content)
        reply = reply.strip() or FALLBACK_REPLY

        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"reply": reply}, status="done"
        )
        return reply
    except Exception:
        logger.exception("team_assistant_failed", extra={"project_id": str(project_id)})
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "team_assistant_failed"}, status="failed"
        )
        return FALLBACK_REPLY
