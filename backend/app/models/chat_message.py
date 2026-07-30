"""
chat_messages — covers all three chat surfaces in the product: the
ingestion chat, the planning chat, and the post-approval coach chat
panel, distinguished by `phase`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

CHAT_PHASES = ("intake", "planning", "coaching")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    phase: Mapped[str] = mapped_column(
        Enum(*CHAT_PHASES, name="chat_phase"), nullable=False
    )

    # user / agent
    role: Mapped[str] = mapped_column(Text, nullable=False)

    # Which node answered; nullable for user messages.
    agent_node: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional free-text name of whoever typed it. No login, so this is
    # NOT a FK — it is display-only (Section 4 — Access Model).
    speaker_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
