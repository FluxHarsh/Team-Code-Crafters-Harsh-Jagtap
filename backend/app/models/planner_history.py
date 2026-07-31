"""
planner_history — Workstream A2. Append-only revision log for every
roadmap/scope rewrite the Planner produces (manual replan, accepted
suggestion, or plan-chat draft update). Never overwritten -- this is
what GET /planner/history reads so the team can see how the plan
evolved rather than only ever seeing the current draft.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlannerHistory(Base):
    __tablename__ = "planner_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    scope_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    roadmap_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
