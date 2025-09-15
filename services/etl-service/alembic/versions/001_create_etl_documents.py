"""Create etl_documents table

Revision ID: 001
Revises:
Create Date: 2025-09-15 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create etl_documents table"""
    op.create_table(
        "etl_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.TEXT(), nullable=True),
        sa.Column("file_name", sa.TEXT(), nullable=False),
        sa.Column("file_type", sa.TEXT(), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lot_id", "file_name", name="uq_etl_documents_lot_id_file_name"
        ),
    )

    # Create full-text search index for Russian language
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_etl_documents_content_fts
        ON etl_documents USING gin(to_tsvector('russian', content))
        """
    )


def downgrade() -> None:
    """Drop etl_documents table"""
    op.drop_table("etl_documents")
