"""Typed CRUD for planner_history (Workstream A2, append-only)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planner_history import PlannerHistory


async def add_revision(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    reason: str,
    scope_snapshot: dict,
    roadmap_snapshot: list,
) -> PlannerHistory:
    revision = PlannerHistory(
        project_id=project_id,
        reason=reason,
        scope_snapshot=scope_snapshot,
        roadmap_snapshot=roadmap_snapshot,
    )
    session.add(revision)
    await session.flush()
    return revision


async def list_revisions_for_project(
    session: AsyncSession, project_id: uuid.UUID
) -> list[PlannerHistory]:
    result = await session.execute(
        select(PlannerHistory)
        .where(PlannerHistory.project_id == project_id)
        .order_by(PlannerHistory.created_at.asc())
    )
    return list(result.scalars().all())
