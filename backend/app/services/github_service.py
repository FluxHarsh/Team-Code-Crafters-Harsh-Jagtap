"""
Orchestrates a single GitHub poll (Implementation Plan Phase 5): fetch
via app.agents.nodes.github_watcher, persist projects.github_state,
sync the CommitFile/MAPS_TO graph, stamp github_connections.last_polled_at,
and hand off to the Risk Watcher (Phase 6's
app.services.risk_service.run_risk_watcher_for_project). Routes call
this instead of touching the watcher/repositories directly, same split
as planning_service.py / roadmap_service.py.

Called two ways:
  - Once, synchronously, right after POST .../github/connect validates
    a new connection -- so github_state is populated immediately
    instead of waiting a full poll_interval_seconds for a scheduler
    that doesn't exist until Phase 10.
  - Later, on a timer, by Phase 10's APScheduler job -- same function,
    same code path, per the Implementation Plan's "one predictable
    code path" goal for the whole GitHub integration.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.github_watcher import run_github_watcher
from app.errors import NotFoundError
from app.repositories import github_connections as github_connections_repo
from app.repositories import graph as graph_repo
from app.repositories import projects as projects_repo
from app.services.github_client import GithubApiError
from app.services.risk_service import run_risk_watcher_for_project

logger = logging.getLogger(__name__)


@dataclass
class PollResult:
    polled: bool
    github_state: dict


async def poll_project(session: AsyncSession, driver: AsyncDriver, project_id: uuid.UUID, *, trigger: str) -> PollResult:
    """Runs one full poll for a project's connected repo. Returns
    polled=False (no-op, not an error) if the project has no GitHub
    connection yet -- callers decide whether that's worth surfacing."""
    connection = await github_connections_repo.get_connection_for_project(session, project_id)
    if connection is None:
        return PollResult(polled=False, github_state={})

    project = await projects_repo.get_project(session, project_id)
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")

    access_token = await github_connections_repo.get_decrypted_token_for_project(session, project_id)
    since = connection.last_polled_at.isoformat() if connection.last_polled_at else None

    try:
        result = await run_github_watcher(
            session,
            project_id=project_id,
            repo_full_name=connection.repo_full_name,
            access_token=access_token,
            roadmap=project.roadmap or [],
            since=since,
            trigger=trigger,
        )
    except GithubApiError:
        logger.exception("github_poll_failed", extra={"project_id": str(project_id)})
        raise

    github_state = result["github_state"]
    matched_commits = result["matched_commits"]

    updated_project = await projects_repo.update_project(session, project_id, github_state=github_state)
    await graph_repo.sync_commit_files(driver, matched_commits)

    await github_connections_repo.mark_polled(session, project_id, polled_at=datetime.now(timezone.utc))

    await run_risk_watcher_for_project(session, driver, updated_project, trigger="github_watcher")

    logger.info("github_poll_done", extra={"project_id": str(project_id), "trigger": trigger})
    return PollResult(polled=True, github_state=github_state)
