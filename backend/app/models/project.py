"""
projects — the core shared-state table (architecture doc Section 3.1).

One row per hackathon project. No team_id / user_id: this MVP runs a
single project workspace with no accounts (Section 4 — Access Model).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PROJECT_STATUSES = (
    "intake",
    "planning",
    "active",
    "at_risk",
    "pitch_ready",
    "submitted",
)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum(*PROJECT_STATUSES, name="project_status"),
        nullable=False,
        default="intake",
        server_default="intake",
    )

    # { raw, refined } — built up across the ingestion chat.
    project_idea: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # { mvp_features: [], cut_features: [], assumptions: [] }
    scope: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # [ { id, task, owner, eta, status } ]
    roadmap: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # [ { id, risk, severity, suggested_fix, resolved } ]
    risks: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # [ { source: manual|github, text, ts } ]
    progress_log: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # { commits: [], open_prs: [], branches: [], issues: [] }
    github_state: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # Generated pitch structure. Nullable until the Pitch Agent runs.
    pitch_outline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # When pitch_outline was last (re)generated. Separate from
    # updated_at (Phase 2->7): updated_at bumps on *any* project write
    # (roadmap edits, risk resolves, etc.), so it can't stand in for
    # "when was the pitch generated" once other writes happen after.
    pitch_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Last Supervisor routing decision.
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    hours_remaining: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Set when the team approves the plan (Section 2.1, step 3) — this
    # is what unlocks the dashboard.
    plan_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
