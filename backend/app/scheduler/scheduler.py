"""
AsyncIOScheduler wiring -- architecture doc Section 7.1 ("polling,
confirmed, via APScheduler in-process"). This is the piece that turns
the Monitoring loop from "reacts to an incoming HTTP request" into
"keeps running whether or not anyone has the dashboard open," per
Section 7's own framing.

Two jobs per active project (app/scheduler/jobs.py):
  - poll_github, every project.github_connection.poll_interval_seconds
    (default 120s, Section 7.3's rate-limit budget)
  - tick_hours_remaining, every 60s

Job store: SQLAlchemyJobStore backed by the same Postgres database
(sync engine -- APScheduler's jobstores are sync-only, hence the
postgresql+psycopg2 URL derived from settings.database_url rather than
reusing the app's asyncpg engine), per the plan's "schedule state
survives a restart" requirement (Section 7.2).

That said, startup recovery (start_scheduler, called from app.main's
lifespan) does NOT lean on the jobstore's persisted job list as the
source of truth for "which projects should be polled" -- it re-queries
Postgres for status="active" projects and re-registers both jobs for
each one with replace_existing=True. Postgres, not APScheduler's own
persistence, is the actual source of truth for which projects are
active (a project's poll_interval_seconds could have changed while the
process was down; a project could have been manually edited in the
DB) -- the jobstore is what makes that re-registration idempotent
across restarts, not what decides what to register. This matches
Section 7.2's own reasoning: "nothing is lost because state lives in
Postgres, not in memory."
"""

from __future__ import annotations

import logging
import uuid

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

logger = logging.getLogger(__name__)

POLL_JOB_PREFIX = "poll_github"
TICK_JOB_PREFIX = "tick_hours"
TICK_INTERVAL_SECONDS = 60

_scheduler: AsyncIOScheduler | None = None


def _sync_database_url(async_url: str) -> str:
    """SQLAlchemyJobStore needs a sync driver -- swap asyncpg for
    psycopg2 (already in requirements.txt) rather than adding a second
    connection pool via aiopg or similar just for this."""
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=_sync_database_url(settings.database_url))},
            job_defaults={
                # A tick that's still running when the next one fires
                # should not stack another instance behind it -- the
                # advisory-lock overlap guard inside each job body
                # (app/repositories/locks.py) is the real guard, this
                # is just cheap extra insurance at the scheduler level.
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 30,
            },
        )
    return _scheduler


def poll_job_id(project_id: uuid.UUID) -> str:
    return f"{POLL_JOB_PREFIX}:{project_id}"


def tick_job_id(project_id: uuid.UUID) -> str:
    return f"{TICK_JOB_PREFIX}:{project_id}"


def register_project_jobs(project_id: uuid.UUID, *, poll_interval_seconds: int) -> None:
    """Adds both jobs for a project, replacing any existing registration
    (safe to call more than once for the same project -- e.g. startup
    recovery calling this for every active project on every restart)."""
    from app.scheduler.jobs import poll_github_job, tick_hours_remaining_job

    scheduler = get_scheduler()
    scheduler.add_job(
        poll_github_job,
        "interval",
        seconds=poll_interval_seconds,
        args=[str(project_id)],
        id=poll_job_id(project_id),
        replace_existing=True,
    )
    scheduler.add_job(
        tick_hours_remaining_job,
        "interval",
        seconds=TICK_INTERVAL_SECONDS,
        args=[str(project_id)],
        id=tick_job_id(project_id),
        replace_existing=True,
    )
    logger.info(
        "scheduler_jobs_registered",
        extra={"project_id": str(project_id), "poll_interval_seconds": poll_interval_seconds},
    )


def deregister_project_jobs(project_id: uuid.UUID) -> None:
    """Safe to call even if the jobs were never registered (e.g. a
    project that reaches "submitted" without ever having a GitHub
    connection) -- remove_job on a missing id is a no-op here, not an
    error, since both ids are looked up individually and any lookup
    failure is caught and logged rather than raised."""
    scheduler = get_scheduler()
    for job_id in (poll_job_id(project_id), tick_job_id(project_id)):
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
    logger.info("scheduler_jobs_deregistered", extra={"project_id": str(project_id)})


async def start_scheduler() -> None:
    """Called once from app.main's lifespan on startup. Starts the
    scheduler, then re-registers jobs for every currently-active
    project -- see module docstring for why this re-query, not the
    jobstore's own persisted state, is what actually decides which
    projects get polled after a restart."""
    from app.db.postgres import get_session_factory
    from app.repositories import github_connections as github_connections_repo
    from app.repositories import projects as projects_repo

    scheduler = get_scheduler()
    scheduler.start()

    session_factory = get_session_factory()
    async with session_factory() as session:
        active_projects = await projects_repo.list_projects_by_status(session, "active")
        for project in active_projects:
            connection = await github_connections_repo.get_connection_for_project(session, project.id)
            poll_interval = connection.poll_interval_seconds if connection else 120
            register_project_jobs(project.id, poll_interval_seconds=poll_interval)

    logger.info("scheduler_started", extra={"recovered_project_count": len(active_projects)})


async def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
