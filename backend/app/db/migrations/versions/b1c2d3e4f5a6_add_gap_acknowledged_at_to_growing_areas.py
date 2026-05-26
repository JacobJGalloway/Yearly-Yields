"""add_gap_acknowledged_at_to_growing_areas

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 00:00:00.000000

Stores the timestamp when a user last acknowledged an NWS data gap for an area.
Null means never acknowledged. Used by the data-gaps endpoint to suppress repeat
notifications for the same gap window.
"""

from alembic import op
import sqlalchemy as sa

revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'growing_areas',
        sa.Column('gap_acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('growing_areas', 'gap_acknowledged_at')
