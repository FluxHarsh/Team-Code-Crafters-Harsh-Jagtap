"""
Intake node -- architecture doc Section 2.1, step 1. Converses with the
team about their problem/solution, decides internally when there's
enough context to hand off to the Planner (ready_for_planning).
"""

import logging

from app.agents.json_utils import parse_json_reply
from app.agents.llm import get_chat_model
from app.agents.prompts import INTAKE_SYSTEM
from app.agents.state import CoachState
from app.repositories import agent_run_log as agent_run_log_repo

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Tell me a bit more -- what problem are you solving, what's your "
    "solution idea, and who's it for? Once I have a clear picture of "
    "those we can move on to planning."
)


async def intake_node(state: CoachState) -> CoachState:
    session = state["session"]
    project_id = state["project_id"]
    project_idea = dict(state.get("project_idea") or {})
    user_message = state["user_message"]

    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="intake",
        trigger=state.get("trigger", "user_action"),
        input_snapshot={"user_message": user_message, "project_idea": project_idea},
    )

    try:
        model = get_chat_model(temperature=0.4)
        raw_context = project_idea.get("raw", "")
        response = await model.ainvoke(
            [
                ("system", INTAKE_SYSTEM),
                (
                    "human",
                    "Context gathered so far (raw transcript excerpt):\n"
                    f"{raw_context or '(nothing yet -- this is the first message)'}\n\n"
                    f"Team's latest message:\n{user_message}",
                ),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = parse_json_reply(content)

        reply = parsed.get("reply") or FALLBACK_REPLY
        ready = bool(parsed.get("ready_for_planning", False))
        refined = parsed.get("refined") or {}
        refined = {k: v for k, v in refined.items() if isinstance(v, str) and v.strip()}

        updated_idea = dict(project_idea)
        updated_idea["raw"] = f"{raw_context}\n{user_message}".strip()
        if refined:
            updated_idea["refined"] = {**updated_idea.get("refined", {}), **refined}

        state["reply"] = reply
        state["ready_for_planning"] = ready
        state["updated_project_idea"] = updated_idea

        await agent_run_log_repo.finish_run(
            session,
            run.id,
            output_snapshot={"reply": reply, "ready_for_planning": ready, "refined": refined},
            status="done",
        )
    except Exception:
        logger.exception("intake_node_failed", extra={"project_id": str(project_id)})
        updated_idea = dict(project_idea)
        updated_idea["raw"] = f"{project_idea.get('raw', '')}\n{user_message}".strip()

        state["reply"] = FALLBACK_REPLY
        state["ready_for_planning"] = False
        state["updated_project_idea"] = updated_idea

        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "intake_node_failed"}, status="failed"
        )

    return state
