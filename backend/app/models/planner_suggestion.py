"""
planner_suggestions — Workstream A3. Risk Watcher / GitHub Watcher never
call the Planner directly; instead the Supervisor writes a row here and
the team explicitly accepts or dismisses it before anything touches the
roadmap. This is what replaces the old "risk detected -> auto-replan"
path.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SUGGESTION_STATUSES = ("pending", "accepted", "dismissed")


class PlannerSuggestion(Base):
    __tablename__ = "planner_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # risk_reprioritization / github_insight / general — what produced
    # this suggestion, so the Planner UI can show the right icon/copy.
    source: Mapped[str] = mapped_column(Text, nullable=False)

    risk_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reprioritizer's decision (drop/extend/reassign) + rationale, or
    # a GitHub-insight-derived suggestion text.
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    # Free-form context snapshot (downstream milestones, github insight
    # payload, etc.) so the accept flow doesn't need to re-derive it.
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    status: Mapped[str] = mapped_column(
        Enum(*SUGGESTION_STATUSES, name="planner_suggestion_status"),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
