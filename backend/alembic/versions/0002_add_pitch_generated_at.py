"""add pitch_generated_at

The Phase 2 stub used projects.updated_at as a stand-in for "when was
the pitch generated" since no dedicated column existed yet -- a latent
bug, since editing the roadmap after generating a pitch would bump
updated_at and make GET .../pitch report a wrong (too-recent)
generated_at. Phase 7 adds the real column.

Revision ID: a1c9f2d7e6b3
Revises: ff23a8c084bc
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1c9f2d7e6b3"
down_revision = "ff23a8c084bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("pitch_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "pitch_generated_at")
