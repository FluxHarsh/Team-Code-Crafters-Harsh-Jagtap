"""
Shared FastAPI dependencies (Phase 2; get_neo4j added Phase 4).

Every router gets its DB session the same way — commit on success,
rollback on any exception (including our own AppError subclasses, which
are raised deliberately and should still roll back any partial writes).
"""

from collections.abc import AsyncGenerator

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session_factory
from app.db.neo4j import get_driver


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_neo4j() -> AsyncDriver:
    """Single shared driver (connection-pooled internally by the neo4j
    package), same instance the lifespan hook in app/main.py warms up
    and disposes -- routes just borrow a reference, they don't own its
    lifecycle."""
    return get_driver()
