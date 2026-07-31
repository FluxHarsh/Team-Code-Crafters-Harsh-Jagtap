"""
GET  /api/v1/projects/{project_id}/planner/suggestions
POST /api/v1/projects/{project_id}/planner/suggestions/{suggestion_id}/accept
POST /api/v1/projects/{project_id}/planner/suggestions/{suggestion_id}/dismiss
GET  /api/v1/projects/{project_id}/planner/history

Workstream A2/A3. This is the only path that turns a Risk Watcher /
GitHub Watcher suggestion into an actual roadmap change (accept ->
roadmap_service.replan_roadmap under the hood) -- the Planner itself
never gets called by a watcher directly. /planner/history is the
append-only revision log every replan_roadmap call now writes to.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncDriver
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.repositories import planner_history as planner_history_repo
from app.repositories import planner_suggestions as planner_suggestions_repo
from app.routers.common import get_project_or_404
from app.services.risk_service import accept_suggestion, dismiss_suggestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["planner"])


class SuggestionOut(BaseModel):
    id: str
    source: str
    risk_id: str | None
    decision: str | None
    rationale: str
    status: str
    created_at: str


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionOut]


class AcceptResponse(BaseModel):
    decision: str
    rationale: str
    roadmap_replanned: bool


class DismissResponse(BaseModel):
    id: str
    status: str


class HistoryEntryOut(BaseModel):
    id: str
    reason: str
    scope_snapshot: dict
    roadmap_snapshot: list
    created_at: str


class HistoryResponse(BaseModel):
    revisions: list[HistoryEntryOut]


@router.get("/{project_id}/planner/suggestions", response_model=SuggestionsResponse)
async def list_suggestions(
    project_id: str,
    status_filter: str | None = Query(default="pending", alias="status"),
    session: AsyncSession = Depends(get_db),
) -> SuggestionsResponse:
    project = await get_project_or_404(session, project_id)
    suggestions = await planner_suggestions_repo.list_suggestions_for_project(
        session, project.id, status=status_filter
    )
    return SuggestionsResponse(
        suggestions=[
            SuggestionOut(
                id=str(s.id),
                source=s.source,
                risk_id=s.risk_id,
                decision=s.decision,
                rationale=s.rationale,
                status=s.status,
                created_at=s.created_at.isoformat(),
            )
            for s in suggestions
        ]
    )


@router.post("/{project_id}/planner/suggestions/{suggestion_id}/accept", response_model=AcceptResponse)
async def post_accept_suggestion(
    project_id: str,
    suggestion_id: str,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> AcceptResponse:
    project = await get_project_or_404(session, project_id)
    result = await accept_suggestion(session, driver, project, uuid.UUID(suggestion_id))
    logger.info("planner suggestion accepted", extra={"project_id": str(project.id), "suggestion_id": suggestion_id})
    return AcceptResponse(decision=result.decision, rationale=result.rationale, roadmap_replanned=result.roadmap_replanned)


@router.post("/{project_id}/planner/suggestions/{suggestion_id}/dismiss", response_model=DismissResponse)
async def post_dismiss_suggestion(
    project_id: str, suggestion_id: str, session: AsyncSession = Depends(get_db)
) -> DismissResponse:
    project = await get_project_or_404(session, project_id)
    suggestion = await dismiss_suggestion(session, project, uuid.UUID(suggestion_id))
    return DismissResponse(id=str(suggestion.id), status=suggestion.status)


@router.get("/{project_id}/planner/history", response_model=HistoryResponse)
async def get_planner_history(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> HistoryResponse:
    project = await get_project_or_404(session, project_id)
    revisions = await planner_history_repo.list_revisions_for_project(session, project.id)
    return HistoryResponse(
        revisions=[
            HistoryEntryOut(
                id=str(r.id),
                reason=r.reason,
                scope_snapshot=r.scope_snapshot,
                roadmap_snapshot=r.roadmap_snapshot,
                created_at=r.created_at.isoformat(),
            )
            for r in revisions
        ]
    )
