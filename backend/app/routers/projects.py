"""
POST /api/v1/projects
GET  /api/v1/projects/{project_id}
POST /api/v1/projects/{project_id}/submit

Architecture doc Section 5.1. Project creation and the full-state read
that the dashboard hydrates from on load. The ingestion/planning/
approval routes that share Section 5.1 live in ingestion.py and
planning.py (mirrors the router-per-domain split in the Implementation
Plan, Phase 2).

Phase 10 adds POST .../submit: projects.status already had "submitted"
as a valid terminal state in the schema (Section 3.1's lifecycle), but
nothing could ever reach it -- this is that transition, and the point
where Phase 10's poll_github/tick_hours_remaining jobs get explicitly
deregistered so a submitted project stops consuming poll budget
(Section 7's "idle projects stop consuming poll budget"). Each job also
self-deregisters defensively if it ever fires for a non-"active"
project (app/scheduler/jobs.py), so this explicit call is a courtesy
for immediate cleanup, not the only thing standing between a submitted
project and a wasted poll.
"""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.errors import ConflictError
from app.repositories import projects as projects_repo
from app.routers.common import get_project_or_404
from app.scheduler.scheduler import deregister_project_jobs
from app.services.project_context import build_project_context, detect_missing_fields, is_complete

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

INGESTION_GREETING = "Tell me about the problem you're solving and your idea for it."


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectCreateResponse(BaseModel):
    project_id: str
    status: str
    greeting: str


class ProjectStateResponse(BaseModel):
    id: str
    name: str
    status: str
    project_idea: dict
    scope: dict
    roadmap: list
    risks: list
    github_state: dict
    hours_remaining: float | None
    next_action: str | None


class ProjectSubmitResponse(BaseModel):
    id: str
    status: str


class ProjectContextResponse(BaseModel):
    hackathon_details: dict
    team: list
    project: dict
    repository: dict | None
    supporting_documents: list
    presentation: dict | None
    design_links: list
    missing_fields: list[str]
    is_complete: bool


@router.post("", response_model=ProjectCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest, session: AsyncSession = Depends(get_db)
) -> ProjectCreateResponse:
    project = await projects_repo.create_project(session, name=body.name)
    logger.info("project created", extra={"project_id": str(project.id)})
    return ProjectCreateResponse(
        project_id=str(project.id), status=project.status, greeting=INGESTION_GREETING
    )


@router.get("/{project_id}", response_model=ProjectStateResponse)
async def get_project_state(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> ProjectStateResponse:
    project = await get_project_or_404(session, project_id)
    return ProjectStateResponse(
        id=str(project.id),
        name=project.name,
        status=project.status,
        project_idea=project.project_idea,
        scope=project.scope,
        roadmap=project.roadmap,
        risks=project.risks,
        github_state=project.github_state,
        hours_remaining=float(project.hours_remaining) if project.hours_remaining is not None else None,
        next_action=project.next_action,
    )


@router.get("/{project_id}/context", response_model=ProjectContextResponse)
async def get_project_context(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> ProjectContextResponse:
    """A1: the assembled ProjectContext plus the explicit Missing
    Information Detector's report -- what the Intake loop gates
    ready_for_planning on, exposed for the frontend to render a
    checklist."""
    project = await get_project_or_404(session, project_id)
    context = await build_project_context(session, project)
    return ProjectContextResponse(
        hackathon_details=context.hackathon_details,
        team=context.team,
        project=context.project,
        repository=context.repository,
        supporting_documents=context.supporting_documents,
        presentation=context.presentation,
        design_links=context.design_links,
        missing_fields=detect_missing_fields(context),
        is_complete=is_complete(context),
    )


@router.post("/{project_id}/submit", response_model=ProjectSubmitResponse)
async def submit_project(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> ProjectSubmitResponse:
    project = await get_project_or_404(session, project_id)

    if project.status in ("intake", "planning"):
        raise ConflictError(f"Cannot submit from status {project.status!r} -- no plan approved yet")
    if project.status == "submitted":
        raise ConflictError("Project is already submitted")

    updated = await projects_repo.update_project(session, project.id, status="submitted")
    deregister_project_jobs(project.id)
    logger.info("project submitted", extra={"project_id": str(project.id)})

    return ProjectSubmitResponse(id=str(project.id), status=updated.status)
