"""add last_harvest_date to growing_area_plots

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-06-20

"""
from alembic import op
import sqlalchemy as sa

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "growing_area_plots",
        sa.Column("last_harvest_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("growing_area_plots", "last_harvest_date")
