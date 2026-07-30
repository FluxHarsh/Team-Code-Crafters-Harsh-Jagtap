"""
The Phase 3 LangGraph skeleton: Supervisor + Intake + Scope Critic +
Planner, wired in-process (no separate agent service/microservice,
per Revision 2 / architecture doc Section 2).

Graph shape:

    START -> supervisor --intake----> intake --------> END
                        \\--planning-> scope_critic -> planner -> END

The graph is compiled once at import time; every request builds a
fresh CoachState dict and calls one of the two entrypoints below.
There is no checkpointer -- state lives in Postgres (non-negotiable,
architecture doc Section 7.2), not in LangGraph memory, so nothing here
persists across invocations except what nodes explicitly write through
app.repositories.
"""

import uuid

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.intake import intake_node
from app.agents.nodes.planner import planner_node
from app.agents.nodes.scope_critic import scope_critic_node
from app.agents.nodes.supervisor import route_after_supervisor, supervisor_node
from app.agents.state import CoachState


def _build_graph():
    graph = StateGraph(CoachState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("intake", intake_node)
    graph.add_node("scope_critic", scope_critic_node)
    graph.add_node("planner", planner_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"intake": "intake", "planning": "scope_critic"},
    )
    graph.add_edge("intake", END)
    graph.add_edge("scope_critic", "planner")
    graph.add_edge("planner", END)

    return graph.compile()


_compiled_graph = _build_graph()


async def run_intake_turn(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    project_idea: dict,
    user_message: str,
) -> CoachState:
    """Invokes the graph down the intake branch. Returns the resulting
    state -- callers read state["reply"], state["ready_for_planning"],
    state["updated_project_idea"]."""
    initial_state: CoachState = {
        "session": session,
        "project_id": project_id,
        "trigger": "user_action",
        "requested_phase": "intake",
        "project_idea": project_idea,
        "user_message": user_message,
    }
    return await _compiled_graph.ainvoke(initial_state)


async def run_replan_turn(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    project_idea: dict,
    scope: dict,
    roadmap: list,
    hours_remaining: float | None,
    prior_critique_texts: list[str],
    reason: str,
    trigger: str = "re-plan",
) -> CoachState:
    """Invokes the Planner node directly -- not through the compiled
    graph's supervisor/scope_critic routing -- since a re-plan (Phase 4:
    POST .../roadmap/replan, and later Phase 6/10's automatic
    Monitoring-loop trigger) is "rebuild the roadmap from current scope
    + hours_remaining," not a fresh planning chat turn with new critique
    generation. Reuses the existing prior_critique_texts as context so
    the rebuild still respects what the Scope Critic has already raised.
    Returns the resulting state -- callers read state["draft_scope"],
    state["draft_roadmap"] (the rebuilt roadmap), state["reply"]."""
    state: CoachState = {
        "session": session,
        "project_id": project_id,
        "trigger": trigger,
        "requested_phase": "planning",
        "project_idea": project_idea,
        "scope": scope,
        "roadmap": roadmap,
        "hours_remaining": hours_remaining,
        "prior_critique_texts": prior_critique_texts,
        "user_message": (
            f"(Re-plan requested: {reason}. No new message from the team -- "
            "rebuild the roadmap from the current scope and hours remaining.)"
        ),
    }
    return await planner_node(state)


async def run_planning_turn(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    project_idea: dict,
    scope: dict,
    roadmap: list,
    hours_remaining: float | None,
    prior_critique_texts: list[str],
    user_message: str,
) -> CoachState:
    """Invokes the graph down the planning branch (scope_critic ->
    planner). Returns the resulting state -- callers read
    state["reply"], state["draft_scope"], state["draft_roadmap"],
    state["new_critiques"]."""
    initial_state: CoachState = {
        "session": session,
        "project_id": project_id,
        "trigger": "user_action",
        "requested_phase": "planning",
        "project_idea": project_idea,
        "scope": scope,
        "roadmap": roadmap,
        "hours_remaining": hours_remaining,
        "prior_critique_texts": prior_critique_texts,
        "user_message": user_message,
    }
    return await _compiled_graph.ainvoke(initial_state)
