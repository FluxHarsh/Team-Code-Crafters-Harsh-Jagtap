"""
Supervisor node.

Phase 3 scope: routing for the ingestion/planning chat is driven
entirely by which endpoint invoked the graph (POST .../ingest/message
vs POST .../plan/chat) via state["requested_phase"] -- there's no
freeform message to classify there.

Phase 8 adds classify_coach_message: real classification of
post-approval coach-chat messages (Section 5.7) into "replan"
(routes to Phase 4's replan_roadmap), "reprioritize" (routes to Phase
6's reprioritize_risk), or "question" (routes to the Team Assistant's
grounded Q&A). Deliberately rule-based, not an LLM call -- same
rules-vs-LLM split already used elsewhere in this codebase (the Risk
Watcher's detection is rules, the Reprioritizer's actual decision is
the LLM call) -- a 3-way "is this an action verb or a question" split
doesn't need a model round-trip before the Team Assistant's own model
call for the actual answer. Called directly by
app/services/coach_chat_service.py, not through supervisor_node/the
compiled StateGraph below (coach chat isn't a chat-turn in that
graph's sense, same reasoning as every other Phase 4-7 direct node
call in this codebase).
"""

import logging
import re

from app.agents.state import CoachState
from app.repositories import agent_run_log as agent_run_log_repo

logger = logging.getLogger(__name__)

_RISK_ID_RE = re.compile(r"\br-[0-9a-f]{6,}\b")

REPLAN_PHRASES = ("re-plan", "re plan", "replan", "rebuild the roadmap", "redo the roadmap", "regenerate the roadmap")
REPRIORITIZE_PHRASES = ("fix this", "fix it", "reprioritize")

# Keyword -> node whose data most likely grounds the answer, for
# question-type messages. Checked in order; first match wins. Not
# exhaustive by design -- a wrong guess here only affects the
# answered_by label on the response, never the (LLM-generated) answer
# text itself.
_ANSWERED_BY_KEYWORDS = (
    (("risk", "flag", "blocked", "stuck"), "risk_watcher"),
    (("commit", "pull request", " pr ", "pr#", "branch", "github"), "github_watcher"),
    (("pitch", "demo flow", "differentiator", "hook"), "pitch_agent"),
    (("task", "roadmap", "eta", "milestone", "plan"), "planner"),
)


def guess_answered_by(message: str) -> str:
    lowered = f" {message.lower()} "
    for keywords, node_name in _ANSWERED_BY_KEYWORDS:
        if any(kw in lowered for kw in keywords):
            return node_name
    return "team_assistant"


def classify_coach_message(message: str, unresolved_risks: list[dict]) -> tuple[str, str | None]:
    """Returns (action, risk_id). action is "replan", "reprioritize", or
    "question". risk_id is only ever meaningful for "reprioritize" --
    resolved either from an explicit risk id mentioned in the message
    (format "r-xxxxxxxx", matching app.agents.nodes.risk_watcher's id
    scheme) or, if the message uses a reprioritize phrase without
    naming one, from there being exactly one unresolved risk to mean by
    "this"/"it". A reprioritize phrase with zero or multiple unresolved
    risks and no explicit id is still classified "reprioritize" but
    with risk_id=None -- app.services.coach_chat_service asks which
    risk was meant rather than guessing wrong and fixing the wrong
    thing (or worse, silently asking the LLM to guess)."""
    lowered = message.lower()
    risk_id_match = _RISK_ID_RE.search(lowered)
    explicit_risk_id = risk_id_match.group(0) if risk_id_match else None

    if any(phrase in lowered for phrase in REPLAN_PHRASES):
        return "replan", None

    if any(phrase in lowered for phrase in REPRIORITIZE_PHRASES):
        if explicit_risk_id:
            return "reprioritize", explicit_risk_id
        if len(unresolved_risks) == 1:
            return "reprioritize", unresolved_risks[0]["id"]
        return "reprioritize", None

    return "question", None


async def supervisor_node(state: CoachState) -> CoachState:
    session = state["session"]
    project_id = state["project_id"]
    requested_phase = state.get("requested_phase", "intake")

    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="supervisor",
        trigger=state.get("trigger", "user_action"),
        input_snapshot={"requested_phase": requested_phase},
    )

    route = "planning" if requested_phase == "planning" else "intake"
    state["route"] = route

    await agent_run_log_repo.finish_run(
        session, run.id, output_snapshot={"route": route}, status="done"
    )
    return state


def route_after_supervisor(state: CoachState) -> str:
    """Conditional-edge selector -- returns one of the node names the
    graph registers an edge for."""
    return state.get("route", "intake")
