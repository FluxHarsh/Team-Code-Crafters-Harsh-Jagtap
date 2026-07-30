"""
Typed CRUD for chat_messages — covers the ingestion chat, planning
chat, and post-approval coach chat panel, distinguished by `phase`.

Phase 9: add_message also broadcasts chat_message (architecture doc
Section 6, { phase, role, content, agent_node }) -- all three chat
surfaces (Phase 3's ingestion/planning, Phase 8's coaching) already
funnel every message through this one function, so hooking the
broadcast here covers all of them at once rather than at each call
site in app/services/{ingestion,planning,coach_chat}_service.py.
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.ws.connection_manager import broadcast


async def add_message(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    phase: str,
    role: str,
    content: str,
    agent_node: str | None = None,
    speaker_name: str | None = None,
) -> ChatMessage:
    message = ChatMessage(
        project_id=project_id,
        phase=phase,
        role=role,
        content=content,
        agent_node=agent_node,
        speaker_name=speaker_name,
    )
    session.add(message)
    await session.flush()
    await broadcast(
        project_id,
        "chat_message",
        {"phase": phase, "role": role, "content": content, "agent_node": agent_node},
    )
    return message


async def list_messages(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    phase: str | None = None,
    limit: int = 200,
) -> list[ChatMessage]:
    stmt = select(ChatMessage).where(ChatMessage.project_id == project_id)
    if phase is not None:
        stmt = stmt.where(ChatMessage.phase == phase)
    stmt = stmt.order_by(ChatMessage.created_at.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@dataclass
class MessagePage:
    messages: list[ChatMessage]
    next_cursor: str | None


def _encode_cursor(message: ChatMessage) -> str:
    raw = f"{message.created_at.isoformat()}|{message.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_at_raw, id_raw = raw.split("|", 1)
    return datetime.fromisoformat(created_at_raw), uuid.UUID(id_raw)


async def list_messages_page(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    phase: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> MessagePage:
    """Keyset pagination on (created_at, id) — Phase 8's "cursor-paginated
    history for the panel" (Section 5.7). Keyset rather than offset so a
    new message arriving between page fetches can never shift an
    already-returned page's contents, and it stays O(limit) regardless
    of how deep into the history the cursor points. The cursor is an
    opaque token (base64 of "created_at|id") — callers should treat it
    as such, not parse it."""
    stmt = select(ChatMessage).where(ChatMessage.project_id == project_id)
    if phase is not None:
        stmt = stmt.where(ChatMessage.phase == phase)
    if cursor is not None:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(ChatMessage.created_at, ChatMessage.id) > (cursor_created_at, cursor_id)
        )
    # Fetch one extra row to know whether a next page exists, without a
    # separate COUNT query.
    stmt = stmt.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if len(rows) > limit:
        page, extra = rows[:limit], rows[limit]
        return MessagePage(messages=page, next_cursor=_encode_cursor(page[-1]))
    return MessagePage(messages=rows, next_cursor=None)
