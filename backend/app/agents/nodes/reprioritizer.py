"""
Reprioritizer node -- architecture doc Section 5.5. Given one flagged
risk and the list of downstream milestones a Neo4j traversal says are
blocked by it, decides drop/extend/reassign and writes a one-sentence
rationale. The only Phase 6 node that calls the LLM -- Section 5.5 is
explicit this needs real judgment ("decide how to fix an open risk...
rather than blindly re-planning"), unlike the Risk Watcher's rule-based
detection.

Like the Planner and Scope Critic, degrades to a safe deterministic
default on a malformed/failed LLM reply rather than raising -- a bad
model turn should still return *a* decision, not 500 the reprioritize
call. Called directly as a plain async function by
app/services/risk_service.py, same pattern as run_replan_turn/
run_github_watcher.

Phase 11 adds real RAG grounding on top of this: before calling the LLM,
retrieves the top-k most similar postmortem snippets
(app/services/rag_service.py, shared with the Scope Critic) for the
flagged risk's description/suggested_fix, and injects them into the
human message as "projects that hit this kind of blocker historically
recovered by..." context, alongside the Neo4j downstream traversal
result, per architecture doc Section 3.2.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.json_utils import parse_json_reply
from app.agents.llm import get_chat_model
from app.agents.prompts import REPRIORITIZER_SYSTEM
from app.repositories import agent_run_log as agent_run_log_repo
from app.services.rag_service import format_snippets_for_prompt, retrieve_similar_postmortems

logger = logging.getLogger(__name__)

RAG_LABEL = "projects that hit this kind of blocker historically recovered by"


def _grounding_query_text(risk: dict) -> str:
    """Builds the text embedded for retrieval -- the risk's own
    description and suggested_fix are what determines which past
    postmortems are "similar," not the downstream milestone list or
    scope (those describe *this* project's structure, not the kind of
    blocker being hit)."""
    description = risk.get("risk") or risk.get("description") or ""
    suggested_fix = risk.get("suggested_fix") or ""
    return f"{description} {suggested_fix}".strip()


VALID_DECISIONS = {"drop", "extend", "reassign"}
DEFAULT_DECISION = "reassign"


@dataclass
class ReprioritizerDecision:
    decision: str
    rationale: str


def _fallback_decision(downstream: list[dict]) -> ReprioritizerDecision:
    if downstream:
        names = ", ".join(d["name"] for d in downstream[:2])
        rationale = f"Fixing this unblocks {len(downstream)} downstream milestone(s) ({names}) -- reassigning for now."
    else:
        rationale = "No downstream milestones depend on this yet -- reassigning to keep the roadmap moving."
    return ReprioritizerDecision(decision=DEFAULT_DECISION, rationale=rationale)


async def run_reprioritizer(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    risk: dict,
    task: dict | None,
    downstream_milestones: list[dict],
    scope: dict,
    hours_remaining: float | None,
    trigger: str,
) -> ReprioritizerDecision:
    retrieved = await retrieve_similar_postmortems(session, _grounding_query_text(risk))
    grounding_block = format_snippets_for_prompt(retrieved, label=RAG_LABEL)

    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="reprioritizer",
        trigger=trigger,
        input_snapshot={
            "risk_id": risk.get("id"),
            "task_id": task.get("id") if task else None,
            "downstream_count": len(downstream_milestones),
            "retrieved_postmortem_count": len(retrieved),
        },
    )

    try:
        model = get_chat_model(temperature=0.2)
        response = await model.ainvoke(
            [
                ("system", REPRIORITIZER_SYSTEM),
                (
                    "human",
                    f"Flagged risk: {risk}\n\n"
                    f"Roadmap task it's tied to: {task}\n\n"
                    f"Downstream milestones (blocked by this task): {downstream_milestones}\n\n"
                    f"Current scope: {scope}\n\n"
                    f"Hours remaining: {hours_remaining}\n\n"
                    f"{grounding_block}",
                ),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = parse_json_reply(content)
        decision = parsed.get("decision")
        rationale = parsed.get("rationale")

        if decision not in VALID_DECISIONS or not isinstance(rationale, str) or not rationale.strip():
            result = _fallback_decision(downstream_milestones)
        else:
            result = ReprioritizerDecision(decision=decision, rationale=rationale.strip())

        await agent_run_log_repo.finish_run(
            session,
            run.id,
            output_snapshot={"decision": result.decision, "rationale": result.rationale},
            status="done",
        )
        return result
    except Exception:
        logger.exception("reprioritizer_failed", extra={"project_id": str(project_id)})
        result = _fallback_decision(downstream_milestones)
        await agent_run_log_repo.finish_run(
            session,
            run.id,
            output_snapshot={"error": "reprioritizer_failed", "fallback_decision": result.decision},
            status="failed",
        )
        return result
