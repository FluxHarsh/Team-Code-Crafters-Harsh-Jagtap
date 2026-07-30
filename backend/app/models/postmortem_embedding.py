"""
postmortem_embeddings — the pgvector RAG store (architecture doc
Section 3.2), same PostgreSQL instance, no standalone vector database.

Grounds the Scope Critic ("teams with a similar idea usually miss X")
and the Reprioritizer ("projects that hit this kind of blocker usually
recovered by doing Y"). Embeddings come from OpenAI
text-embedding-3-small (1536 dims) — a separate API key from the
LLM key used for agent reasoning.

This table is seeded ahead of the hackathon via scripts/seed_postmortems.py
(curated past-postmortem text) — it is not written to live during the
event.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIM = 1536


class PostmortemEmbedding(Base):
    __tablename__ = "postmortem_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # The original post-mortem / failure-pattern chunk.
    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    # OpenAI text-embedding-3-small.
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    # { tags: [], hackathon_theme, outcome }
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
