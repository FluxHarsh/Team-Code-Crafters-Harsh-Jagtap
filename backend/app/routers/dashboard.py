"""
GET /api/v1/projects/{project_id}/dashboard/overview
GET /api/v1/projects/{project_id}/dashboard/timeline
GET /api/v1/projects/{project_id}/dashboard/kanban
GET /api/v1/projects/{project_id}/dashboard/health
GET /api/v1/projects/{project_id}/dashboard/team-status
GET /api/v1/projects/{project_id}/dashboard/activity-feed
GET /api/v1/projects/{project_id}/dashboard/recommendations

Spec doc Section 8. Gated on plan_approved_at (Workstream A13: the
dashboard is only meaningful once a plan exists) -- returns 409 before
that, same error class every other "not ready yet" route in this
codebase uses.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.errors import ConflictError
from app.models.project import Project
from app.routers.common import get_project_or_404
from app.services import dashboard_service

router = APIRouter(prefix="/api/v1/projects", tags=["dashboard"])


def _require_approved(project: Project) -> None:
    if project.plan_approved_at is None:
        raise ConflictError("Dashboard unlocks only after the Planner draft is approved")


class DashboardOverviewResponse(BaseModel):
    project_id: str
    name: str
    status: str
    percent_complete: int
    hours_remaining: float | None
    open_risks: int
    team_size: int


class TimelineResponse(BaseModel):
    tasks: list[dict]


class KanbanResponse(BaseModel):
    summary: dict
    nodes: list[dict]
    edges: list[dict]


class HealthResponse(BaseModel):
    health_status: str
    open_risk_count: int
    github_insight_count: int
    hours_remaining: float | None


class TeamStatusResponse(BaseModel):
    members: list[dict]


class ActivityFeedResponse(BaseModel):
    events: list[dict]


class RecommendationsResponse(BaseModel):
    recommendations: list[dict]


@router.get("/{project_id}/dashboard/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(project_id: str, session: AsyncSession = Depends(get_db)) -> DashboardOverviewResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    return DashboardOverviewResponse(**dashboard_service.overview(project))


@router.get("/{project_id}/dashboard/timeline", response_model=TimelineResponse)
async def get_dashboard_timeline(project_id: str, session: AsyncSession = Depends(get_db)) -> TimelineResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    return TimelineResponse(tasks=dashboard_service.timeline(project))


@router.get("/{project_id}/dashboard/kanban", response_model=KanbanResponse)
async def get_dashboard_kanban(project_id: str, session: AsyncSession = Depends(get_db)) -> KanbanResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    return KanbanResponse(**dashboard_service.kanban(project))


@router.get("/{project_id}/dashboard/health", response_model=HealthResponse)
async def get_dashboard_health(project_id: str, session: AsyncSession = Depends(get_db)) -> HealthResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    return HealthResponse(**dashboard_service.health(project))


@router.get("/{project_id}/dashboard/team-status", response_model=TeamStatusResponse)
async def get_dashboard_team_status(project_id: str, session: AsyncSession = Depends(get_db)) -> TeamStatusResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    return TeamStatusResponse(members=dashboard_service.team_status(project))


@router.get("/{project_id}/dashboard/activity-feed", response_model=ActivityFeedResponse)
async def get_dashboard_activity_feed(project_id: str, session: AsyncSession = Depends(get_db)) -> ActivityFeedResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    return ActivityFeedResponse(events=dashboard_service.activity_feed(project))


@router.get("/{project_id}/dashboard/recommendations", response_model=RecommendationsResponse)
async def get_dashboard_recommendations(project_id: str, session: AsyncSession = Depends(get_db)) -> RecommendationsResponse:
    project = await get_project_or_404(session, project_id)
    _require_approved(project)
    recs = await dashboard_service.recommendations(session, project)
    return RecommendationsResponse(recommendations=recs)
