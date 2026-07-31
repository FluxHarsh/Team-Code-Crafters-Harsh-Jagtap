"""
POST /api/v1/projects/{project_id}/reprioritize

Architecture doc Section 5.5. Usually auto-triggered by the Risk
Watcher (once Phase 10's scheduler exists); exposed so the coach chat
panel's "fix this" command uses the same code path.

Phase 6: real now, via app/services/risk_service.py -- Neo4j downstream
traversal, the Reprioritizer's drop/extend/reassign call, Phase 4's
replan_roadmap, and marking the risk resolved.
"""

import logging

from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.routers.common import get_project_or_404
from app.services.risk_service import propose_reprioritization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["reprioritize"])


class ReprioritizeRequest(BaseModel):
    risk_id: str


class ReprioritizeResponse(BaseModel):
    suggestion_id: str
    status: str
    decision: str | None
    rationale: str


@router.post("/{project_id}/reprioritize", response_model=ReprioritizeResponse)
async def post_reprioritize(
    project_id: str,
    body: ReprioritizeRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> ReprioritizeResponse:
    """A3: this no longer applies the change -- it proposes it. The
    Reprioritizer still decides drop/extend/reassign, but the result is
    a pending planner_suggestions row; POST
    .../planner/suggestions/{id}/accept is what actually replans."""
    project = await get_project_or_404(session, project_id)

    result = await propose_reprioritization(session, driver, project, body.risk_id, reason="manual_request")

    logger.info(
        "reprioritize proposed",
        extra={"project_id": str(project.id), "risk_id": body.risk_id, "suggestion_id": result.id},
    )
    return ReprioritizeResponse(
        suggestion_id=result.id, status=result.status, decision=result.decision, rationale=result.rationale
    )
