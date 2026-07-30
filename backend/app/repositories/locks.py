"""
Postgres advisory-lock helper.

Phase 4 needed a "409 if a re-plan is already in flight" guard for the
manual POST .../roadmap/replan route (architecture doc Section 5.2).
A transaction-scoped advisory lock (pg_try_advisory_xact_lock) is the
right tool here: it's non-blocking (try, don't wait), it's released
automatically at commit/rollback so it can never be leaked by a crash
mid-request, and it needs no new table/migration.

Phase 10 reuses the exact same primitive for the scheduler's overlap
guard (Section 7.2: "a slow LangGraph run isn't double-triggered by the
next tick") -- as long as a scheduled job's entire body runs inside one
session/transaction (app/scheduler/jobs.py does), the lock's lifetime
naturally spans the whole job, which is exactly what's needed: no
separate is_running column, no manual cleanup on crash, since the lock
releases itself the moment that job's transaction ends one way or
another.

hashtext() gives a stable 32-bit hash of the lock key string, so the
same key always maps to the same lock without needing to parse it into
an integer ourselves. Different prefixes (roadmap_replan, poll_github,
tick_hours) keep each concern's locks from colliding with each other
for the same project_id.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def try_acquire_lock(session: AsyncSession, key: str) -> bool:
    """Non-blocking. Returns True if the lock was acquired, False if
    another in-flight transaction already holds this exact key.
    Released automatically when the current transaction commits or
    rolls back."""
    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"), {"key": key}
    )
    return bool(result.scalar())


async def try_acquire_replan_lock(session: AsyncSession, project_id: uuid.UUID) -> bool:
    """Released at the end of the request, via app.dependencies.get_db."""
    return await try_acquire_lock(session, f"roadmap_replan:{project_id}")


async def try_acquire_poll_lock(session: AsyncSession, project_id: uuid.UUID) -> bool:
    """Phase 10's overlap guard for poll_github_job -- released at the
    end of that job's own session/transaction (app/scheduler/jobs.py),
    which spans the full GitHub Watcher -> Risk Watcher -> Reprioritizer
    -> Planner chain a poll can trigger."""
    return await try_acquire_lock(session, f"poll_github:{project_id}")


async def try_acquire_tick_lock(session: AsyncSession, project_id: uuid.UUID) -> bool:
    """Guards tick_hours_remaining_job the same way -- overlap here is
    lower-stakes (just a decrement + a threshold check) than a poll, but
    the lock is nearly free and prevents a double-decrement if a tick
    ever runs long."""
    return await try_acquire_lock(session, f"tick_hours:{project_id}")
