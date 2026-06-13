"""add growing_area_plot_id to sensor_readings and alerts

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-13

Add nullable growing_area_plot_id FK to sensor_readings and alerts. NOT NULL is
enforced after backfill in migration b5c6d7e8f9a0.
"""

from alembic import op
import sqlalchemy as sa

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sensor_readings",
        sa.Column("growing_area_plot_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "sensor_readings_growing_area_plot_id_fkey",
        "sensor_readings",
        "growing_area_plots",
        ["growing_area_plot_id"],
        ["id"],
    )

    op.add_column(
        "alerts",
        sa.Column("growing_area_plot_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "alerts_growing_area_plot_id_fkey",
        "alerts",
        "growing_area_plots",
        ["growing_area_plot_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("alerts_growing_area_plot_id_fkey", "alerts", type_="foreignkey")
    op.drop_column("alerts", "growing_area_plot_id")

    op.drop_constraint("sensor_readings_growing_area_plot_id_fkey", "sensor_readings", type_="foreignkey")
    op.drop_column("sensor_readings", "growing_area_plot_id")
