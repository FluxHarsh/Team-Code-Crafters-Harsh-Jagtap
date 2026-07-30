"""
Typed CRUD for the projects table (the shared-state row every agent
node reads/writes).

Phase 9: update_project also broadcasts state_updated (architecture
doc Section 6, { path, value }) once per changed field -- every
service in this codebase writes project state exclusively through
this one function, so hooking the broadcast here covers roadmap/scope/
risks/github_state/pitch_outline/status/etc. writes from every phase
at once, including the richer phase-specific events (task_moved,
risk_flagged, plan_approved, ...) that are broadcast separately and on
purpose overlap with this generic one -- the client is expected to
ignore events it doesn't render on the current screen (Section 6).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.ws.connection_manager import broadcast


async def create_project(session: AsyncSession, *, name: str) -> Project:
    project = Project(name=name)
    session.add(project)
    await session.flush()
    return project


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    return await session.get(Project, project_id)


async def get_project_for_update(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """Same lookup as get_project, but takes a row-level lock (SELECT ...
    FOR UPDATE) held for the rest of the transaction. Used by the Kanban
    PATCH route's read-modify-write on the roadmap JSONB array (Phase 4)
    so two concurrent task edits can't clobber each other — the second
    request simply waits for the first request's transaction to commit
    before reading, rather than both reading the same stale array and
    one write overwriting the other."""
    result = await session.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def list_projects_by_status(session: AsyncSession, status: str) -> list[Project]:
    """Used by Phase 10's scheduler startup recovery to find every
    project that should have active poll_github/tick_hours_remaining
    jobs after a restart (status="active")."""
    result = await session.execute(select(Project).where(Project.status == status))
    return list(result.scalars().all())


async def update_project(
    session: AsyncSession, project_id: uuid.UUID, **fields
) -> Project | None:
    """Partial update — pass only the columns that changed, e.g.
    update_project(session, pid, status='active', next_action='planner')."""
    project = await session.get(Project, project_id)
    if project is None:
        return None
    for key, value in fields.items():
        setattr(project, key, value)
    project.updated_at = datetime.now(timezone.utc)
    await session.flush()
    for key, value in fields.items():
        await broadcast(project_id, "state_updated", {"path": key, "value": value})
    return project


async def approve_plan(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """Sets plan_approved_at — this is what unlocks the dashboard
    (architecture doc Section 2.1, step 3)."""
    return await update_project(
        session, project_id, plan_approved_at=datetime.now(timezone.utc)
    )


async def delete_project(session: AsyncSession, project_id: uuid.UUID) -> bool:
    project = await session.get(Project, project_id)
    if project is None:
        return False
    await session.delete(project)
    await session.flush()
    return True
