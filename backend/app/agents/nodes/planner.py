"""
Planner node -- architecture doc Section 2.1, step 2. Proposes/revises
scope + roadmap during the planning chat, taking into account the Scope
Critic's critiques (both prior turns' and this turn's, written just
before this node runs).
"""

import logging

from app.agents.json_utils import parse_json_reply
from app.agents.llm import get_chat_model
from app.agents.prompts import PLANNER_SYSTEM
from app.agents.state import CoachState
from app.repositories import agent_run_log as agent_run_log_repo

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "I hit a snag revising the plan just now -- the draft below is "
    "unchanged from before. Try rephrasing, or ask again in a moment."
)


async def planner_node(state: CoachState) -> CoachState:
    session = state["session"]
    project_id = state["project_id"]
    scope = state.get("scope") or {}
    roadmap = state.get("roadmap") or []

    critique_texts = list(state.get("prior_critique_texts") or [])
    critique_texts.extend(c["critique_text"] for c in state.get("new_critiques") or [])

    input_snapshot = {
        "project_idea": state.get("project_idea", {}),
        "scope": scope,
        "roadmap": roadmap,
        "critiques": critique_texts,
        "user_message": state.get("user_message", ""),
    }
    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="planner",
        trigger=state.get("trigger", "user_action"),
        input_snapshot=input_snapshot,
    )

    try:
        model = get_chat_model(temperature=0.3)
        critiques_block = "\n".join(f"- {t}" for t in critique_texts) or "(none yet)"
        response = await model.ainvoke(
            [
                ("system", PLANNER_SYSTEM),
                (
                    "human",
                    f"Project idea: {state.get('project_idea', {})}\n\n"
                    f"Current draft scope: {scope}\n\n"
                    f"Current draft roadmap: {roadmap}\n\n"
                    f"Hours remaining: {state.get('hours_remaining')}\n\n"
                    f"Scope Critic critiques so far:\n{critiques_block}\n\n"
                    f"Team's latest message: {state.get('user_message', '')}",
                ),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = parse_json_reply(content)

        reply = parsed.get("reply") or FALLBACK_REPLY
        draft_scope = parsed.get("draft_scope")
        draft_roadmap = parsed.get("draft_roadmap")

        if not isinstance(draft_scope, dict):
            draft_scope = scope
        if not isinstance(draft_roadmap, list):
            draft_roadmap = roadmap

        state["reply"] = reply
        state["draft_scope"] = draft_scope
        state["draft_roadmap"] = draft_roadmap

        await agent_run_log_repo.finish_run(
            session,
            run.id,
            output_snapshot={"reply": reply, "draft_scope": draft_scope, "draft_roadmap": draft_roadmap},
            status="done",
        )
    except Exception:
        logger.exception("planner_node_failed", extra={"project_id": str(project_id)})
        state["reply"] = FALLBACK_REPLY
        state["draft_scope"] = scope
        state["draft_roadmap"] = roadmap

        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "planner_node_failed"}, status="failed"
        )

    return state
