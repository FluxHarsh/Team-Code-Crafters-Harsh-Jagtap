"""
POST /api/v1/projects/{project_id}/plan/chat
GET  /api/v1/projects/{project_id}/plan/draft
POST /api/v1/projects/{project_id}/plan/approve

Architecture doc Section 5.1. Steps 2-3 of the demo flow (Section
2.1): the Planner takes over the same chat, then the team explicitly
approves, which is the single trigger point Phase 10's scheduler picks
up (plan_approved_at).

Phase 3: plan/chat routes to the real Scope Critic + Planner nodes
(LangGraph skeleton, app/agents/graph.py) via
app/services/planning_service.py -- the Scope Critic runs first and
writes critique_history rows, then the Planner incorporates them into
its reply/draft. plan/approve now also rejects a second approve
(status must be "planning", not just "not intake") so double-approve
returns 409 rather than silently re-stamping plan_approved_at.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.errors import ConflictError
from app.repositories import github_connections as github_connections_repo
from app.repositories import projects as projects_repo
from app.routers.common import get_project_or_404
from app.scheduler.scheduler import register_project_jobs
from app.services.planning_service import handle_plan_chat
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["planning"])


class PlanChatRequest(BaseModel):
    message: str = Field(min_length=1)
    speaker_name: str | None = Field(
        default=None, description="Display-only, not a credential (Section 4)."
    )


class PlanChatResponse(BaseModel):
    reply: str
    draft_scope: dict
    draft_roadmap: list


class PlanDraftResponse(BaseModel):
    draft_scope: dict
    draft_roadmap: list


class PlanApproveResponse(BaseModel):
    status: str
    plan_approved_at: str
    dashboard_ready: bool


@router.post("/{project_id}/plan/chat", response_model=PlanChatResponse)
async def post_plan_chat(
    project_id: str, body: PlanChatRequest, session: AsyncSession = Depends(get_db)
) -> PlanChatResponse:
    project = await get_project_or_404(session, project_id)

    result = await handle_plan_chat(session, project, body.message, speaker_name=body.speaker_name)

    return PlanChatResponse(
        reply=result.reply, draft_scope=result.draft_scope, draft_roadmap=result.draft_roadmap
    )


@router.get("/{project_id}/plan/draft", response_model=PlanDraftResponse)
async def get_plan_draft(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> PlanDraftResponse:
    project = await get_project_or_404(session, project_id)
    return PlanDraftResponse(draft_scope=project.scope, draft_roadmap=project.roadmap)


@router.post("/{project_id}/plan/approve", response_model=PlanApproveResponse)
async def post_plan_approve(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> PlanApproveResponse:
    project = await get_project_or_404(session, project_id)

    if project.status == "intake":
        raise ConflictError("Plan not ready — still in ingestion")
    if project.status != "planning":
        # Covers double-approve (status already "active" or later) --
        # Phase 12's error-path checklist calls this out explicitly.
        raise ConflictError(f"Plan cannot be approved from status {project.status!r}")

    approved_at = datetime.now(timezone.utc)
    updated = await projects_repo.update_project(
        session, project.id, status="active", plan_approved_at=approved_at, next_action="supervisor"
    )
    logger.info("plan approved", extra={"project_id": str(project.id)})

    # Distinct from the generic state_updated events update_project
    # already fired for status/plan_approved_at/next_action -- this is
    # the specific signal Section 6 says the client uses to transition
    # from the chat screen to the dashboard, not just "something changed".
    await broadcast(
        project.id, "plan_approved", {"plan_approved_at": approved_at.isoformat()}
    )

    # Phase 10: this is the registration point Section 7's Monitoring
    # loop depends on -- from here, the project gets polled/ticked
    # whether or not anyone has the dashboard open. No GitHub connection
    # yet at approval time is fine: poll_github_job's own no-op path
    # (app/services/github_service.py's poll_project) just does nothing
    # useful until the team calls .../github/connect, and re-registering
    # then would be redundant, not required, since a no-op poll is
    # cheap (Section 7.3's rate-limit budget has room to spare).
    connection = await github_connections_repo.get_connection_for_project(session, project.id)
    poll_interval = connection.poll_interval_seconds if connection else 120
    register_project_jobs(project.id, poll_interval_seconds=poll_interval)

    return PlanApproveResponse(
        status=updated.status,
        plan_approved_at=approved_at.isoformat(),
        dashboard_ready=True,
    )
