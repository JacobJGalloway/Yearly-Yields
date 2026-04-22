"""add nws and greenhouse fields to growing_areas

Revision ID: b5e7d0f4c1a9
Revises: a8c3f1e9b2d6
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b5e7d0f4c1a9'
down_revision: Union[str, None] = 'a8c3f1e9b2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('growing_areas', sa.Column('nws_station_id', sa.String(10), nullable=True))
    op.add_column('growing_areas', sa.Column('temp_offset_f', sa.Float(), nullable=True))
    op.add_column('growing_areas', sa.Column('humidity_offset_pct', sa.Float(), nullable=True))
    op.add_column('growing_areas', sa.Column('target_temp_f', sa.Float(), nullable=True))
    op.add_column('growing_areas', sa.Column('target_humidity_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('growing_areas', 'target_humidity_pct')
    op.drop_column('growing_areas', 'target_temp_f')
    op.drop_column('growing_areas', 'humidity_offset_pct')
    op.drop_column('growing_areas', 'temp_offset_f')
    op.drop_column('growing_areas', 'nws_station_id')
