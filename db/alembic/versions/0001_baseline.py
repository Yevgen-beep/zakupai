"""Baseline migration

Revision ID: 0001
Revises:
Create Date: 2025-08-26

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This is a baseline migration - all tables already exist
    pass


def downgrade() -> None:
    # Cannot downgrade from baseline
    pass
