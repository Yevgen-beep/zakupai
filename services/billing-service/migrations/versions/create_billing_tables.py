"""create billing tables

Revision ID: 001_create_billing
Revises:
Create Date: 2025-10-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_create_billing'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create billing schema and tables."""
    # Create billing schema
    op.execute('CREATE SCHEMA IF NOT EXISTS billing')

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("email", sa.String(255)),
        sa.Column("plan", sa.String(50), nullable=False, default="free"),
        sa.Column("status", sa.String(20), nullable=False, default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("billing.users.id")),
        sa.Column("key", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        schema="billing",
    )

    # Create usage table
    op.create_table(
        "usage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("api_key_id", sa.Integer, sa.ForeignKey("billing.api_keys.id")),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("requests", sa.Integer, nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )


def downgrade():
    """Drop billing tables and schema."""
    op.drop_table("usage", schema="billing")
    op.drop_table("api_keys", schema="billing")
    op.drop_table("users", schema="billing")
    op.execute('DROP SCHEMA IF EXISTS billing CASCADE')
