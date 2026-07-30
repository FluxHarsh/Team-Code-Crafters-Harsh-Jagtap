"""
agent_run_log — one row per LangGraph node execution. Powers the
"Agent graph view" lighting up the active node, and gives a debug trail
for judges/demo Q&A.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentRunLog(Base):
    __tablename__ = "agent_run_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # supervisor / intake / scope_critic / planner / github_watcher /
    # risk_watcher / reprioritizer / pitch_agent
    node_name: Mapped[str] = mapped_column(Text, nullable=False)

    # user_action / scheduled_poll / re-plan
    trigger: Mapped[str] = mapped_column(Text, nullable=False)

    input_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    output_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # running / done / failed
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="running", server_default="running"
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
