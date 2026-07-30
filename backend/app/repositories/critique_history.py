"""Typed CRUD for the critique_history table (append-only)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.critique_history import CritiqueHistory


async def add_critique(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    category: str,
    critique_text: str,
) -> CritiqueHistory:
    critique = CritiqueHistory(
        project_id=project_id, category=category, critique_text=critique_text
    )
    session.add(critique)
    await session.flush()
    return critique


async def list_critiques_for_project(
    session: AsyncSession, project_id: uuid.UUID, *, category: str | None = None
) -> list[CritiqueHistory]:
    """Lets the Scope Critic / Planner ask "what have I already told
    this team" without loading/parsing the whole projects row."""
    stmt = select(CritiqueHistory).where(CritiqueHistory.project_id == project_id)
    if category is not None:
        stmt = stmt.where(CritiqueHistory.category == category)
    stmt = stmt.order_by(CritiqueHistory.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
