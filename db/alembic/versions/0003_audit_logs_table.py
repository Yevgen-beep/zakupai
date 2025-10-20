"""audit_logs table

Revision ID: 0003
Revises: 0002
Create Date: 2025-08-26

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id bigserial PRIMARY KEY,
            service text NOT NULL,
            route text NOT NULL,
            method text NOT NULL,
            status int NOT NULL,
            req_id text,
            ip text,
            duration_ms int,
            payload_hash text,
            error text,
            created_at timestamp DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_audit_logs_service_created_at
        ON audit_logs (service, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_audit_logs_req_id
        ON audit_logs (req_id) WHERE req_id IS NOT NULL;
    """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
