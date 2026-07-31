"""Typed CRUD for chat_attachments (Workstream A6)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_attachment import ChatAttachment


async def create_attachment(
    session: AsyncSession, *, message_id: uuid.UUID, document_id: uuid.UUID
) -> ChatAttachment:
    attachment = ChatAttachment(message_id=message_id, document_id=document_id)
    session.add(attachment)
    await session.flush()
    return attachment


async def list_for_message(
    session: AsyncSession, message_id: uuid.UUID
) -> list[ChatAttachment]:
    result = await session.execute(
        select(ChatAttachment).where(ChatAttachment.message_id == message_id)
    )
    return list(result.scalars().all())
