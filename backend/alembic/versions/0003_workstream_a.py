"""Workstream A: planner suggestions/history, chat split + attachments,
ProjectContext columns

Adds:
  - planner_suggestions, planner_history tables (A2/A3 -- suggestion ->
    accept/dismiss flow replacing the old auto-replan path)
  - chat_attachments table + chat_messages.chat_scope/mentions_ai (A5/A6
    -- personal/group chat split, file intake from chat)
  - projects.hackathon_details / projects.team (A1 -- ProjectContext)

No existing data touched or dropped; every new column has a safe
default so existing rows backfill cleanly.

Revision ID: b7e3d1a94f02
Revises: a1c9f2d7e6b3
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7e3d1a94f02"
down_revision = "a1c9f2d7e6b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- A1: ProjectContext columns on projects ---
    op.add_column(
        "projects",
        sa.Column(
            "hackathon_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "team",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )

    # --- A5: chat split columns on chat_messages ---
    chat_scope_enum = postgresql.ENUM("personal", "group", name="chat_scope")
    chat_scope_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "chat_messages",
        sa.Column(
            "chat_scope",
            chat_scope_enum,
            nullable=False,
            server_default="group",
        ),
    )
    op.add_column(
        "chat_messages",
        sa.Column(
            "mentions_ai", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # --- A6: chat_attachments ---
    op.create_table(
        "chat_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chat_attachments_message_id", "chat_attachments", ["message_id"]
    )

    # --- A3: planner_suggestions ---
    # Note: unlike chat_scope above (added via a bare add_column, which
    # needs the type pre-created), this enum is used inside
    # create_table() below, which creates the backing type itself --
    # calling .create() here too would double-CREATE TYPE and error.
    suggestion_status_enum = postgresql.ENUM(
        "pending", "accepted", "dismissed", name="planner_suggestion_status"
    )
    op.create_table(
        "planner_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("risk_id", sa.Text(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status", suggestion_status_enum, nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_planner_suggestions_project_id", "planner_suggestions", ["project_id"]
    )

    # --- A2: planner_history ---
    op.create_table(
        "planner_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "scope_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "roadmap_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_planner_history_project_id", "planner_history", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_planner_history_project_id", table_name="planner_history")
    op.drop_table("planner_history")

    op.drop_index("ix_planner_suggestions_project_id", table_name="planner_suggestions")
    op.drop_table("planner_suggestions")
    postgresql.ENUM(name="planner_suggestion_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_chat_attachments_message_id", table_name="chat_attachments")
    op.drop_table("chat_attachments")

    op.drop_column("chat_messages", "mentions_ai")
    op.drop_column("chat_messages", "chat_scope")
    postgresql.ENUM(name="chat_scope").drop(op.get_bind(), checkfirst=True)

    op.drop_column("projects", "team")
    op.drop_column("projects", "hackathon_details")
