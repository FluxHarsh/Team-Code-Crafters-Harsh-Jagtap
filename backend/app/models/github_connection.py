"""
github_connections — one repo per project for the MVP. If a team's
submission spans multiple repos, point this at the primary/demo repo.

access_token is stored encrypted at rest (Fernet, see
app/security.py) — the repository layer (app/repositories/
github_connections.py) is the only place that encrypts/decrypts it.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GithubConnection(Base):
    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # One repo per project — UNIQUE, not just indexed.
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # e.g. "team/hackpilot"
    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)

    # Encrypted GitHub personal access token (ciphertext, not plaintext).
    access_token: Mapped[str] = mapped_column(Text, nullable=False)

    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, server_default="120"
    )
