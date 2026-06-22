"""add growing_area_plot_id to yield_plans

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-20

YieldPlan is the only agronomic record still missing growing_area_plot_id after
the Week 1 migration. Add the FK, backfill via join to crop_cycles (which already
has growing_area_plot_id NOT NULL), then enforce NOT NULL for consistency with
alerts, sensor_readings, and crop_cycles.
"""

import sqlalchemy as sa
from alembic import op

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "yield_plans",
        sa.Column("growing_area_plot_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "yield_plans_growing_area_plot_id_fkey",
        "yield_plans",
        "growing_area_plots",
        ["growing_area_plot_id"],
        ["id"],
    )

    op.execute("""
        UPDATE yield_plans yp
        SET growing_area_plot_id = cc.growing_area_plot_id
        FROM crop_cycles cc
        WHERE yp.crop_cycle_id = cc.id
    """)

    op.execute("ALTER TABLE yield_plans ALTER COLUMN growing_area_plot_id SET NOT NULL")


def downgrade() -> None:
    op.drop_constraint(
        "yield_plans_growing_area_plot_id_fkey", "yield_plans", type_="foreignkey"
    )
    op.drop_column("yield_plans", "growing_area_plot_id")
