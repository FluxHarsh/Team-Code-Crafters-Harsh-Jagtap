"""
Shared state shape for the Phase 3 LangGraph skeleton (Supervisor +
Intake + Scope Critic + Planner).

This graph is compiled once at import time but *invoked* fresh for
every HTTP request (no checkpointer, no cross-request persistence —
state lives in Postgres per the architecture doc's non-negotiables,
not in LangGraph memory). Because each invocation is scoped to a
single request, it's safe to carry the live AsyncSession through the
state dict itself rather than inventing a second plumbing mechanism —
nodes still only ever touch app.repositories with it, never raw SQL or
the ORM directly (Phase 1's rule).
"""

from __future__ import annotations

import uuid
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession


class CoachState(TypedDict, total=False):
    # --- request-scoped plumbing (not agent content) ---
    session: AsyncSession
    project_id: uuid.UUID
    trigger: str  # user_action / scheduled_poll / re-plan (agent_run_log.trigger)

    # --- routing ---
    requested_phase: str  # "intake" | "planning" -- which endpoint invoked the graph
    route: str  # set by the supervisor node

    # --- inputs (read from the projects row + repos before invoking) ---
    user_message: str
    project_idea: dict
    scope: dict
    roadmap: list
    hours_remaining: float | None
    prior_critique_texts: list[str]

    # --- intake node output ---
    reply: str
    ready_for_planning: bool
    updated_project_idea: dict

    # --- scope critic node output ---
    new_critiques: list[dict]  # [{category, critique_text}]

    # --- planner node output ---
    draft_scope: dict
    draft_roadmap: list
