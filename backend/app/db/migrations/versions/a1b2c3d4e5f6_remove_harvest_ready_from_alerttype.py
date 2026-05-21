"""remove_harvest_ready_from_alerttype

Revision ID: a1b2c3d4e5f6
Revises: f4c3b2a1d0e9
Create Date: 2026-05-20 00:00:00.000000

harvest_ready belongs in a notification/event system (v1.2), not the anomaly
alert system. This migration removes the value from the PostgreSQL enum.
PostgreSQL does not support DROP VALUE, so we recreate the type.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f4c3b2a1d0e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove any harvest_ready rows before dropping the enum value.
    op.execute("DELETE FROM alerts WHERE alert_type = 'harvest_ready'")

    # PostgreSQL cannot DROP a value from an existing enum — recreate the type.
    op.execute("""
        CREATE TYPE alerttype_new AS ENUM (
            'temperature_high', 'temperature_low',
            'humidity_high', 'humidity_low', 'combined'
        )
    """)
    op.execute("""
        ALTER TABLE alerts
            ALTER COLUMN alert_type TYPE alerttype_new
            USING alert_type::text::alerttype_new
    """)
    op.execute("DROP TYPE alerttype")
    op.execute("ALTER TYPE alerttype_new RENAME TO alerttype")


def downgrade() -> None:
    # Restore harvest_ready (deleted rows are not recoverable).
    op.execute("""
        CREATE TYPE alerttype_new AS ENUM (
            'temperature_high', 'temperature_low',
            'humidity_high', 'humidity_low', 'combined', 'harvest_ready'
        )
    """)
    op.execute("""
        ALTER TABLE alerts
            ALTER COLUMN alert_type TYPE alerttype_new
            USING alert_type::text::alerttype_new
    """)
    op.execute("DROP TYPE alerttype")
    op.execute("ALTER TYPE alerttype_new RENAME TO alerttype")
