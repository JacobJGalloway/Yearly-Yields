"""update growing_area_plots schema

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2026-06-13

Add plot_index (INTEGER, nullable until backfill), harvest_weekdays (INTEGER[]),
make name nullable and widen to 100 chars to support sentinel rows (open-field
plot_index=0 rows have null name).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d1e2f3a4b5c6"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "growing_area_plots",
        sa.Column("plot_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "growing_area_plots",
        sa.Column("harvest_weekdays", postgresql.ARRAY(sa.Integer()), nullable=True),
    )
    # Widen name to 100 chars and make nullable (sentinel rows have null name)
    op.alter_column(
        "growing_area_plots",
        "name",
        existing_type=sa.String(length=25),
        type_=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "growing_area_plots",
        "name",
        existing_type=sa.String(length=100),
        type_=sa.String(length=25),
        nullable=False,
    )
    op.drop_column("growing_area_plots", "harvest_weekdays")
    op.drop_column("growing_area_plots", "plot_index")
