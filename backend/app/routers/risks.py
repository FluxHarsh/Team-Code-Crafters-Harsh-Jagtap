"""
POST /api/v1/projects/{project_id}/progress
GET  /api/v1/projects/{project_id}/risks
POST /api/v1/projects/{project_id}/risks/{risk_id}/resolve

Architecture doc Section 5.4. Progress logging feeds the same Risk
Watcher as GitHub polling; risks live inline as a JSONB list on
projects.risks (Section 3.1), same pattern as roadmap tasks.

Phase 6: progress now actually triggers the Risk Watcher (via
app/services/risk_service.py) instead of always returning
risk_watcher_triggered: false, and resolve also marks the matching
Risk node resolved in Neo4j, not just the JSONB row.

Phase 9: resolve now goes through risk_service.resolve_risk (shared
with reprioritize_risk's own auto-resolve) instead of duplicating the
JSONB update inline, so the risk_resolved broadcast (Section 6) fires
from exactly one place regardless of which path resolved it.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.repositories import projects as projects_repo
from app.routers.common import get_project_or_404
from app.services.risk_service import resolve_risk, run_risk_watcher_for_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["risks"])


class ProgressRequest(BaseModel):
    text: str = Field(min_length=1)


class ProgressResponse(BaseModel):
    logged: bool
    risk_watcher_triggered: bool


class RisksResponse(BaseModel):
    risks: list


class RiskResolveRequest(BaseModel):
    resolution_note: str | None = None


class RiskResolveResponse(BaseModel):
    id: str
    resolved: bool


@router.post(
    "/{project_id}/progress", response_model=ProgressResponse, status_code=status.HTTP_201_CREATED
)
async def post_progress(
    project_id: str,
    body: ProgressRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> ProgressResponse:
    project = await get_project_or_404(session, project_id)

    entry = {
        "source": "manual",
        "text": body.text,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    progress_log = list(project.progress_log or [])
    progress_log.append(entry)
    project = await projects_repo.update_project(session, project.id, progress_log=progress_log)
    logger.info("progress logged", extra={"project_id": str(project.id)})

    risk_watcher_triggered = True
    try:
        await run_risk_watcher_for_project(session, driver, project, trigger="user_action")
    except Exception:
        # Same isolation as the connect route's first poll (Phase 5):
        # the progress entry is already logged and that's the primary
        # thing this call promises -- a Risk Watcher hiccup shouldn't
        # turn a successful log into a 500. Already logged with a
        # stack trace + agent_run_log(status="failed") inside
        # run_risk_watcher itself.
        logger.warning("risk watcher failed after progress log", extra={"project_id": str(project.id)})
        risk_watcher_triggered = False

    return ProgressResponse(logged=True, risk_watcher_triggered=risk_watcher_triggered)


@router.get("/{project_id}/risks", response_model=RisksResponse)
async def get_risks(project_id: str, session: AsyncSession = Depends(get_db)) -> RisksResponse:
    project = await get_project_or_404(session, project_id)
    return RisksResponse(risks=project.risks)


@router.post("/{project_id}/risks/{risk_id}/resolve", response_model=RiskResolveResponse)
async def post_resolve_risk(
    project_id: str,
    risk_id: str,
    body: RiskResolveRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> RiskResolveResponse:
    project = await get_project_or_404(session, project_id)

    await resolve_risk(session, driver, project, risk_id, resolution_note=body.resolution_note)
    logger.info("risk resolved", extra={"project_id": str(project.id), "risk_id": risk_id})

    return RiskResolveResponse(id=risk_id, resolved=True)
