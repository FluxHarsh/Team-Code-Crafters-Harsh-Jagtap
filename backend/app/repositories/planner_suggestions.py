"""Typed CRUD for planner_suggestions (Workstream A3)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planner_suggestion import PlannerSuggestion


async def create_suggestion(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    source: str,
    risk_id: str | None,
    decision: str | None,
    rationale: str,
    context: dict | None = None,
) -> PlannerSuggestion:
    suggestion = PlannerSuggestion(
        project_id=project_id,
        source=source,
        risk_id=risk_id,
        decision=decision,
        rationale=rationale,
        context=context or {},
    )
    session.add(suggestion)
    await session.flush()
    return suggestion


async def get_suggestion(
    session: AsyncSession, suggestion_id: uuid.UUID
) -> PlannerSuggestion | None:
    return await session.get(PlannerSuggestion, suggestion_id)


async def list_suggestions_for_project(
    session: AsyncSession, project_id: uuid.UUID, *, status: str | None = None
) -> list[PlannerSuggestion]:
    stmt = select(PlannerSuggestion).where(PlannerSuggestion.project_id == project_id)
    if status is not None:
        stmt = stmt.where(PlannerSuggestion.status == status)
    stmt = stmt.order_by(PlannerSuggestion.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def set_status(
    session: AsyncSession, suggestion_id: uuid.UUID, status: str
) -> PlannerSuggestion | None:
    suggestion = await session.get(PlannerSuggestion, suggestion_id)
    if suggestion is None:
        return None
    suggestion.status = status
    suggestion.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return suggestion
