"""
Pitch Agent node -- architecture doc Section 5.6. Synthesizes
{hook, problem, solution, demo_flow[], differentiator, ask} from
project_idea, scope, resolved risks, and the final roadmap state.
hook/ask extend Section 5.6's example response shape per the
Implementation Plan Phase 7 task list ("plus a hook/ask, matching the
shape used in the dashboard's pitch panel") -- a JSONB-native
extension, same as depends_on (Phase 4) and the extra risk bookkeeping
fields (Phase 6).

Falls back to a deterministic outline assembled directly from
project_idea/scope on a malformed/failed LLM reply, same pattern as
the Planner/Scope Critic/Reprioritizer -- a bad model turn should still
hand the team *something* to work with this close to the deadline, not
500 the one call that matters most right before demos.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.json_utils import parse_json_reply
from app.agents.llm import get_chat_model
from app.agents.prompts import PITCH_AGENT_SYSTEM
from app.repositories import agent_run_log as agent_run_log_repo

logger = logging.getLogger(__name__)

REQUIRED_STRING_FIELDS = ("hook", "problem", "solution", "differentiator", "ask")


@dataclass
class PitchOutline:
    hook: str
    problem: str
    solution: str
    demo_flow: list[str] = field(default_factory=list)
    differentiator: str = ""
    ask: str = ""


def _fallback_outline(*, project_idea: dict, scope: dict) -> PitchOutline:
    refined = project_idea.get("refined") or {}
    problem = refined.get("problem") or project_idea.get("raw") or "Problem statement not yet captured."
    solution = refined.get("solution") or "Solution summary not yet captured."
    mvp_features = scope.get("mvp_features") or []
    return PitchOutline(
        hook=f"We built {solution[:80]}" if solution else "Here's what we built.",
        problem=problem,
        solution=solution,
        demo_flow=[f"Show {feat}" for feat in mvp_features[:5]] or ["Walk through the working demo"],
        differentiator="Built end-to-end during the hackathon window.",
        ask="Feedback from judges on where to take this next.",
    )


def _valid(parsed: dict) -> bool:
    if not all(isinstance(parsed.get(f), str) and parsed[f].strip() for f in REQUIRED_STRING_FIELDS):
        return False
    demo_flow = parsed.get("demo_flow")
    return isinstance(demo_flow, list) and all(isinstance(s, str) for s in demo_flow)


async def run_pitch_agent(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    project_idea: dict,
    scope: dict,
    resolved_risks: list[dict],
    roadmap: list[dict],
    trigger: str,
) -> PitchOutline:
    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="pitch_agent",
        trigger=trigger,
        input_snapshot={
            "resolved_risk_count": len(resolved_risks),
            "roadmap_task_count": len(roadmap),
        },
    )

    try:
        model = get_chat_model(temperature=0.4)
        response = await model.ainvoke(
            [
                ("system", PITCH_AGENT_SYSTEM),
                (
                    "human",
                    f"Project idea: {project_idea}\n\n"
                    f"Current scope: {scope}\n\n"
                    f"Resolved risks (obstacles overcome): {resolved_risks}\n\n"
                    f"Final roadmap state: {roadmap}",
                ),
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = parse_json_reply(content)

        if _valid(parsed):
            outline = PitchOutline(
                hook=parsed["hook"].strip(),
                problem=parsed["problem"].strip(),
                solution=parsed["solution"].strip(),
                demo_flow=[s.strip() for s in parsed["demo_flow"] if s.strip()],
                differentiator=parsed["differentiator"].strip(),
                ask=parsed["ask"].strip(),
            )
        else:
            outline = _fallback_outline(project_idea=project_idea, scope=scope)

        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"pitch_outline": outline.__dict__}, status="done"
        )
        return outline
    except Exception:
        logger.exception("pitch_agent_failed", extra={"project_id": str(project_id)})
        outline = _fallback_outline(project_idea=project_idea, scope=scope)
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "pitch_agent_failed"}, status="failed"
        )
        return outline
