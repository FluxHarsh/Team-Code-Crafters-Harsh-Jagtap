"""
The two scheduled job bodies (architecture doc Section 7, Implementation
Plan Phase 10). Both:
  - run their entire body inside one session/transaction (so the
    advisory-lock overlap guard's lifetime naturally spans the whole
    job -- see app/repositories/locks.py)
  - re-check project.status at the top and self-deregister + return
    early if it's no longer "active" (a defensive safety net alongside
    the explicit deregister call on POST .../submit -- see
    app/routers/projects.py -- so jobs stop even if that call was
    somehow missed)
  - are wrapped in an outer try/except that logs and swallows any
    exception rather than re-raising it: per Section 7.2, "one
    project's crash must never take down the scheduler for others."
    Node-level failures already get their own agent_run_log(status=
    "failed") row from that node's own start_run/finish_run pair
    (every node in this codebase has done this since Phase 3) -- this
    outer catch is a last-resort net for anything that goes wrong
    *outside* a node (e.g. the DB itself being briefly unreachable),
    not a substitute for that per-node logging.

Called directly by name (APScheduler needs a picklable, importable
reference for the SQLAlchemyJobStore) rather than as closures, and take
a plain str project_id (not uuid.UUID) since that's what round-trips
cleanly through the jobstore's serialization.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from app.db.neo4j import get_driver
from app.db.postgres import get_session_factory
from app.errors import ConflictError
from app.repositories import projects as projects_repo
from app.repositories.locks import try_acquire_poll_lock, try_acquire_tick_lock
from app.scheduler.scheduler import TICK_INTERVAL_SECONDS, deregister_project_jobs
from app.services.github_service import poll_project
from app.services.pitch_service import generate_pitch, is_pitch_ready

logger = logging.getLogger(__name__)


async def poll_github_job(project_id_str: str) -> None:
    project_id = uuid.UUID(project_id_str)
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            try:
                project = await projects_repo.get_project(session, project_id)
                if project is None or project.status != "active":
                    deregister_project_jobs(project_id)
                    return

                if not await try_acquire_poll_lock(session, project_id):
                    logger.info("poll_github_job_skipped_already_running", extra={"project_id": project_id_str})
                    return

                driver = get_driver()
                await poll_project(session, driver, project_id, trigger="scheduled_poll")
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception:
        logger.exception("poll_github_job_failed", extra={"project_id": project_id_str})


async def tick_hours_remaining_job(project_id_str: str) -> None:
    project_id = uuid.UUID(project_id_str)
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            try:
                project = await projects_repo.get_project(session, project_id)
                if project is None or project.status != "active":
                    deregister_project_jobs(project_id)
                    return

                if not await try_acquire_tick_lock(session, project_id):
                    return

                if project.hours_remaining is not None:
                    decrement = Decimal(TICK_INTERVAL_SECONDS) / Decimal(3600)
                    new_hours = max(Decimal("0"), Decimal(project.hours_remaining) - decrement)
                    project = await projects_repo.update_project(session, project_id, hours_remaining=new_hours)

                hours_remaining = float(project.hours_remaining) if project.hours_remaining is not None else None
                if project.pitch_outline is None and is_pitch_ready(project.roadmap or [], hours_remaining):
                    try:
                        await generate_pitch(session, project, trigger="scheduled_poll")
                        logger.info("pitch_auto_triggered", extra={"project_id": project_id_str})
                    except ConflictError:
                        # is_pitch_ready and generate_pitch's own check
                        # can only disagree in a narrow race (another
                        # write changed roadmap/hours between the two
                        # reads within this same transaction) -- next
                        # tick will just re-evaluate.
                        pass

                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except Exception:
        logger.exception("tick_hours_remaining_job_failed", extra={"project_id": project_id_str})
