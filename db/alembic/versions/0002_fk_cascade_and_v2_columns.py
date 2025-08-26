"""FK CASCADE and v2 columns

Revision ID: 0002
Revises: 0001
Create Date: 2025-08-26

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add v2 columns to lots table
    op.execute(
        """
        ALTER TABLE lots
          ADD COLUMN IF NOT EXISTS risk_score numeric,
          ADD COLUMN IF NOT EXISTS deadline date,
          ADD COLUMN IF NOT EXISTS customer_bin text,
          ADD COLUMN IF NOT EXISTS plan_id text;
    """
    )

    # Update FK constraints with CASCADE
    op.execute(
        """
        ALTER TABLE lot_prices DROP CONSTRAINT IF EXISTS lot_prices_lot_id_fkey;
        ALTER TABLE lot_prices DROP CONSTRAINT IF EXISTS lot_prices_price_id_fkey;
        ALTER TABLE lot_prices
          ADD CONSTRAINT lot_prices_lot_id_fkey
            FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE;
        ALTER TABLE lot_prices
          ADD CONSTRAINT lot_prices_price_id_fkey
            FOREIGN KEY (price_id) REFERENCES prices(id) ON DELETE CASCADE;
    """
    )


def downgrade() -> None:
    # Leave empty for simplicity as specified
    pass
