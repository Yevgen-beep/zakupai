"""Create etl_batch_uploads table

Revision ID: 001
Revises:
Create Date: 2025-09-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create etl_batch_uploads table"""
    op.create_table(
        "etl_batch_uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bin", sa.String(length=12), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("batch_id", UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop etl_batch_uploads table"""
    op.drop_table("etl_batch_uploads")
