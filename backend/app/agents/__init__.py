"""
LangGraph agent layer (Implementation Plan Phase 3).

One in-process LangGraph graph (app.agents.graph) with four nodes —
Supervisor, Intake, Scope Critic, Planner — matching architecture doc
Section 2.1 steps 1-2 (ingestion -> planning). Routes never import
from here directly for DB access; nodes only ever touch
app.repositories, same rule as every other layer (Phase 1).
"""
