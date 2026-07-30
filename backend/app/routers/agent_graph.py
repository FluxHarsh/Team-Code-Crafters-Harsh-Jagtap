"""
GET /api/v1/projects/{project_id}/agent-graph/state

Architecture doc Section 5.8. Powers the live agent graph view — which
node is currently active, plus recent run history from agent_run_log
(Phase 1 table, populated starting Phase 3).

Real data source already: this reads agent_run_log via the Phase 1
repo, so the response is genuinely empty (no active_node, no runs)
until later phases start writing to that table — not hardcoded stub
data.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories import agent_run_log as agent_run_log_repo
from app.routers.common import get_project_or_404

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["agent-graph"])


class AgentRunOut(BaseModel):
    node: str
    trigger: str
    finished_at: str | None


class AgentGraphStateResponse(BaseModel):
    active_node: str | None
    recent_runs: list[AgentRunOut]


@router.get("/{project_id}/agent-graph/state", response_model=AgentGraphStateResponse)
async def get_agent_graph_state(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> AgentGraphStateResponse:
    project = await get_project_or_404(session, project_id)
    runs = await agent_run_log_repo.list_runs_for_project(session, project.id, limit=20)

    active = next((r for r in runs if r.status == "running"), None)

    return AgentGraphStateResponse(
        active_node=active.node_name if active else None,
        recent_runs=[
            AgentRunOut(
                node=r.node_name,
                trigger=r.trigger,
                finished_at=r.finished_at.isoformat() if r.finished_at else None,
            )
            for r in runs
        ],
    )
