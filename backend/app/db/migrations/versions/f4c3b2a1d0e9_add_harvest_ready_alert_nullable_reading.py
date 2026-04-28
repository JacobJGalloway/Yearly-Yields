"""add_harvest_ready_alert_nullable_reading

Revision ID: f4c3b2a1d0e9
Revises: e9f2a3b1c4d5
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f4c3b2a1d0e9'
down_revision: Union[str, None] = 'e9f2a3b1c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE alerttype ADD VALUE IF NOT EXISTS 'harvest_ready'")
    op.alter_column(
        'alerts',
        'triggering_reading_id',
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL.
    # Restoring NOT NULL would fail if any harvest_ready alerts (null reading) exist.
    pass
