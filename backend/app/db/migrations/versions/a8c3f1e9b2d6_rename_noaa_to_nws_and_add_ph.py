"""rename noaa to nws and add ph to sensor_readings

Revision ID: a8c3f1e9b2d6
Revises: d3b8e91c0f24
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a8c3f1e9b2d6'
down_revision: Union[str, None] = 'd3b8e91c0f24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE readingsource RENAME VALUE 'noaa' TO 'nws'")
    op.add_column('sensor_readings', sa.Column('ph', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('sensor_readings', 'ph')
    op.execute("ALTER TYPE readingsource RENAME VALUE 'nws' TO 'noaa'")
