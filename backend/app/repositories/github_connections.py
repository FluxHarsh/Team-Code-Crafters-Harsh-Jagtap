"""
Typed CRUD for github_connections. This is the ONLY layer that should
ever see a plaintext GitHub token — it encrypts on write and decrypts
on the one read path that needs the real token (the poll scheduler).
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_connection import GithubConnection
from app.security import decrypt_token, encrypt_token


async def upsert_connection(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    repo_full_name: str,
    access_token_plaintext: str,
    poll_interval_seconds: int = 120,
) -> GithubConnection:
    """One repo per project — updates in place if a connection already
    exists for this project (project_id is UNIQUE)."""
    result = await session.execute(
        select(GithubConnection).where(GithubConnection.project_id == project_id)
    )
    connection = result.scalar_one_or_none()

    encrypted = encrypt_token(access_token_plaintext)

    if connection is None:
        connection = GithubConnection(
            project_id=project_id,
            repo_full_name=repo_full_name,
            access_token=encrypted,
            poll_interval_seconds=poll_interval_seconds,
        )
        session.add(connection)
    else:
        connection.repo_full_name = repo_full_name
        connection.access_token = encrypted
        connection.poll_interval_seconds = poll_interval_seconds

    await session.flush()
    return connection


async def get_connection_for_project(
    session: AsyncSession, project_id: uuid.UUID
) -> GithubConnection | None:
    result = await session.execute(
        select(GithubConnection).where(GithubConnection.project_id == project_id)
    )
    return result.scalar_one_or_none()


async def get_decrypted_token_for_project(
    session: AsyncSession, project_id: uuid.UUID
) -> str | None:
    """Used only by the poll scheduler (Section 7.1) — every other
    consumer should never need the plaintext token."""
    connection = await get_connection_for_project(session, project_id)
    if connection is None:
        return None
    return decrypt_token(connection.access_token)


async def mark_polled(
    session: AsyncSession, project_id: uuid.UUID, *, polled_at: datetime
) -> GithubConnection | None:
    connection = await get_connection_for_project(session, project_id)
    if connection is None:
        return None
    connection.last_polled_at = polled_at
    await session.flush()
    return connection
