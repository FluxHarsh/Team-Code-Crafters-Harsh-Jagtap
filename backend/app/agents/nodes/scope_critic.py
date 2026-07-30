"""
Scope Critic node -- runs inside every planning turn (not its own
route, per Implementation Plan Phase 3), right before the Planner node.
Writes critique_history rows directly so "what have I already told this
team" survives across turns without bloating the hot projects row
(architecture doc Section 3.1), and passes this turn's fresh critiques
into state so the Planner reacts to them immediately too.

Phase 11 adds real RAG grounding on top of this: before calling the LLM,
retrieves the top-k most similar postmortem snippets
(app/services/rag_service.py, shared with the Reprioritizer) for the
project idea + draft scope, and injects them into the human message as
"similar teams historically missed..." context, per architecture doc
Section 3.2.
"""

import logging

from app.agents.json_utils import parse_json_reply
from app.agents.llm import get_chat_model
from app.agents.prompts import SCOPE_CRITIC_SYSTEM
from app.agents.state import CoachState
from app.repositories import agent_run_log as agent_run_log_repo
from app.repositories import critique_history as critique_history_repo
from app.services.rag_service import format_snippets_for_prompt, retrieve_similar_postmortems

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"scope_gap", "overscope", "assumption"}
RAG_LABEL = "similar teams historically missed"


def _grounding_query_text(project_idea: dict, scope: dict) -> str:
    """Builds the text embedded for retrieval -- the project idea and
    draft scope are what actually determines which past postmortems are
    "similar," not the team's latest chat message (which might just be
    "sounds good" or a one-word reply with no scoping content)."""
    idea_text = project_idea.get("raw") or project_idea.get("summary") or ""
    scope_text = scope.get("summary") or scope.get("mvp_features") or ""
    return f"{idea_text} {scope_text}".strip()


async def scope_critic_node(state: CoachState) -> CoachState:
    session = state["session"]
    project_id = state["project_id"]
    project_idea = state.get("project_idea", {})
    scope = state.get("scope", {})

    retrieved = await retrieve_similar_postmortems(
        session, _grounding_query_text(project_idea, scope)
    )
    grounding_block = format_snippets_for_prompt(retrieved, label=RAG_LABEL)

    input_snapshot = {
        "project_idea": project_idea,
        "scope": scope,
        "roadmap": state.get("roadmap", []),
        "user_message": state.get("user_message", ""),
        "retrieved_postmortem_count": len(retrieved),
    }
    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="scope_critic",
        trigger=state.get("trigger", "user_action"),
        input_snapshot=input_snapshot,
    )

    new_critiques: list[dict] = []
    try:
        model = get_chat_model(temperature=0.2)
        response = await model.ainvoke(
            [
                ("system", SCOPE_CRITIC_SYSTEM),
                (
                    "human",
                    f"Project idea: {project_idea}\n\n"
                    f"Current draft scope: {scope}\n\n"
                    f"Current draft roadmap: {state.get('roadmap', [])}\n\n"
                    f"Team's latest message: {state.get('user_message', '')}\n\n"
                    f"{grounding_block}",
                ),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = parse_json_reply(content)
        raw_critiques = parsed.get("critiques") or []

        for item in raw_critiques:
            if not isinstance(item, dict):
                continue
            category = item.get("category")
            text = item.get("critique_text")
            if category in VALID_CATEGORIES and isinstance(text, str) and text.strip():
                new_critiques.append({"category": category, "critique_text": text.strip()})

        for critique in new_critiques:
            await critique_history_repo.add_critique(
                session,
                project_id=project_id,
                category=critique["category"],
                critique_text=critique["critique_text"],
            )

        state["new_critiques"] = new_critiques
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"new_critiques": new_critiques}, status="done"
        )
    except Exception:
        logger.exception("scope_critic_node_failed", extra={"project_id": str(project_id)})
        state["new_critiques"] = []
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "scope_critic_node_failed"}, status="failed"
        )

    return state
