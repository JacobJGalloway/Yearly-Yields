"""add forecasted_end_date to crop_cycles

Revision ID: d3b8e91c0f24
Revises: ca974954e4a4
Create Date: 2026-04-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd3b8e91c0f24'
down_revision: Union[str, None] = 'ca974954e4a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'crop_cycles',
        sa.Column('forecasted_end_date', sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('crop_cycles', 'forecasted_end_date')
