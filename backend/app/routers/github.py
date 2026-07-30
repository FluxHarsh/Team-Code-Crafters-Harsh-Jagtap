"""
POST /api/v1/projects/{project_id}/github/connect
GET  /api/v1/projects/{project_id}/github/state

Architecture doc Section 5.3. Polling, not webhooks (Section 7.1) — no
public callback URL to keep alive during the demo.

Phase 5: connect now validates the token/repo against the live GitHub
API (401 invalid token, 422 repo not found or no access) before
storing anything, then immediately runs one poll synchronously via
app/services/github_service.py -- so github_state is populated right
after connecting instead of waiting for Phase 10's scheduler to exist.
A failure in that first poll is logged but doesn't fail the connect
call itself: the token/repo were already validated, so the connection
is legitimate even if this particular poll had a transient hiccup: the
next poll (manual, or Phase 10's scheduler) will retry.

Phase 10: if the project is already "active" (plan approved before
connecting -- the common order, since GitHub usually isn't set up
until after planning), connect also re-registers the scheduled
poll_github job with this connection's real poll_interval_seconds --
approval registered it with a 120s default (no connection existed yet
to read a real value from), so this call is what corrects it to
whatever was actually requested here.
"""

import logging
import re

from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.errors import UnauthorizedError, UnprocessableEntityError
from app.repositories import github_connections as github_connections_repo
from app.routers.common import get_project_or_404
from app.scheduler.scheduler import register_project_jobs
from app.services import github_client
from app.services.github_service import poll_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["github"])

REPO_FULL_NAME_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


class GithubConnectRequest(BaseModel):
    repo_full_name: str = Field(min_length=3)
    access_token: str = Field(min_length=1)
    poll_interval_seconds: int = Field(default=120, ge=30)


class GithubConnectResponse(BaseModel):
    connected: bool
    poll_interval_seconds: int


class GithubStateResponse(BaseModel):
    commits: list
    open_prs: list
    issues: list
    last_polled_at: str | None


@router.post("/{project_id}/github/connect", response_model=GithubConnectResponse)
async def post_github_connect(
    project_id: str,
    body: GithubConnectRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> GithubConnectResponse:
    project = await get_project_or_404(session, project_id)

    if not REPO_FULL_NAME_RE.match(body.repo_full_name):
        # Section 5.3 documents 422 for "repo not found or no access" —
        # a malformed owner/repo string is the closest we can get to
        # that without even calling the GitHub API.
        raise UnprocessableEntityError(f"Malformed repo_full_name: {body.repo_full_name!r}")

    access_result = await github_client.check_repo_access(body.access_token, body.repo_full_name)
    if not access_result.ok:
        if access_result.status_code == 401:
            raise UnauthorizedError("Invalid GitHub token")
        raise UnprocessableEntityError(f"Repo not found or no access: {body.repo_full_name!r}")

    connection = await github_connections_repo.upsert_connection(
        session,
        project_id=project.id,
        repo_full_name=body.repo_full_name,
        access_token_plaintext=body.access_token,
        poll_interval_seconds=body.poll_interval_seconds,
    )
    logger.info("github connection stored", extra={"project_id": str(project.id)})

    if project.status == "active":
        register_project_jobs(project.id, poll_interval_seconds=connection.poll_interval_seconds)

    try:
        await poll_project(session, driver, project.id, trigger="user_action")
    except Exception:
        # Already logged with a stack trace inside poll_project/
        # run_github_watcher (and recorded as agent_run_log
        # status="failed") -- connect itself still succeeds.
        logger.warning(
            "initial poll after connect failed, will retry on next poll",
            extra={"project_id": str(project.id)},
        )

    return GithubConnectResponse(
        connected=True, poll_interval_seconds=connection.poll_interval_seconds
    )


@router.get("/{project_id}/github/state", response_model=GithubStateResponse)
async def get_github_state(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> GithubStateResponse:
    project = await get_project_or_404(session, project_id)
    state = project.github_state or {}
    return GithubStateResponse(
        commits=state.get("commits", []),
        open_prs=state.get("open_prs", []),
        issues=state.get("issues", []),
        last_polled_at=state.get("last_polled_at"),
    )
