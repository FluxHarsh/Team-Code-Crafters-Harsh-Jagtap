"""initial schema

Creates the six core relational tables (architecture doc Section 3.1)
plus the pgvector RAG store (Section 3.2):
  projects, documents, critique_history, github_connections,
  agent_run_log, chat_messages, postmortem_embeddings

Revision ID: ff23a8c084bc
Revises:
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "ff23a8c084bc"
down_revision = None
branch_labels = None
depends_on = None

# create_type=False: we create these types ourselves (below) with an
# explicit checkfirst-guarded call. Without this, SQLAlchemy also tries
# to emit its own CREATE TYPE when the enum is used as a column type in
# create_table(), producing a duplicate (and, in `--sql` offline mode,
# an unconditional one since checkfirst can't query a live DB there).
PROJECT_STATUS_ENUM = postgresql.ENUM(
    "intake",
    "planning",
    "active",
    "at_risk",
    "pitch_ready",
    "submitted",
    name="project_status",
    create_type=False,
)

CHAT_PHASE_ENUM = postgresql.ENUM(
    "intake",
    "planning",
    "coaching",
    name="chat_phase",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # pgvector extension for the postmortem_embeddings table (Section 3.2).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    PROJECT_STATUS_ENUM.create(bind, checkfirst=True)
    CHAT_PHASE_ENUM.create(bind, checkfirst=True)

    # --- projects ------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "status",
            PROJECT_STATUS_ENUM,
            nullable=False,
            server_default="intake",
        ),
        sa.Column(
            "project_idea", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("scope", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("roadmap", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risks", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "progress_log", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "github_state", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("pitch_outline", postgresql.JSONB(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("hours_remaining", sa.Numeric(5, 2), nullable=True),
        sa.Column("plan_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- documents -------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])

    # --- critique_history ------------------------------------------------
    op.create_table(
        "critique_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("critique_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_critique_history_project_id", "critique_history", ["project_id"]
    )

    # --- github_connections ------------------------------------------------
    op.create_table(
        "github_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("repo_full_name", sa.Text(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "poll_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
    )

    # --- agent_run_log ------------------------------------------------
    op.create_table(
        "agent_run_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column(
            "input_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("output_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="running"
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_run_log_project_id", "agent_run_log", ["project_id"])

    # --- chat_messages ------------------------------------------------
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", CHAT_PHASE_ENUM, nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("agent_node", sa.Text(), nullable=True),
        sa.Column("speaker_name", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_chat_messages_project_id", "chat_messages", ["project_id"])

    # --- postmortem_embeddings (pgvector RAG store, Section 3.2) --------
    op.create_table(
        "postmortem_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        "CREATE INDEX ix_postmortem_embeddings_embedding "
        "ON postmortem_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("postmortem_embeddings")
    op.drop_index("ix_chat_messages_project_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_agent_run_log_project_id", table_name="agent_run_log")
    op.drop_table("agent_run_log")
    op.drop_table("github_connections")
    op.drop_index("ix_critique_history_project_id", table_name="critique_history")
    op.drop_table("critique_history")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("projects")

    bind = op.get_bind()
    CHAT_PHASE_ENUM.drop(bind, checkfirst=True)
    PROJECT_STATUS_ENUM.drop(bind, checkfirst=True)

    op.execute("DROP EXTENSION IF EXISTS vector")
