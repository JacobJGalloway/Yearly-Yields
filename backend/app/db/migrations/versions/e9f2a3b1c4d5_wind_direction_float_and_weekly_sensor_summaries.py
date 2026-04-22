"""wind_direction float and weekly_sensor_summaries table

Revision ID: e9f2a3b1c4d5
Revises: dc1d3a48956d
Create Date: 2026-04-21

Changes:
  - sensor_readings.wind_direction: String(3) compass → Float degrees (0.0–359.99)
    Existing compass string values are nullified before type change.
  - New table: weekly_sensor_summaries (write-once quarterly aggregate)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e9f2a3b1c4d5"
down_revision: Union[str, None] = "dc1d3a48956d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Compass strings cannot cast to float — null them before altering type.
    op.execute("UPDATE sensor_readings SET wind_direction = NULL WHERE wind_direction IS NOT NULL")
    op.alter_column(
        "sensor_readings",
        "wind_direction",
        existing_type=sa.String(length=3),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="NULL::double precision",
    )

    op.create_table(
        "weekly_sensor_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("growing_area_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("avg_temperature", sa.Float(), nullable=True),
        sa.Column("avg_humidity", sa.Float(), nullable=True),
        sa.Column("avg_ph", sa.Float(), nullable=True),
        sa.Column("avg_wind_speed", sa.Float(), nullable=True),
        sa.Column("avg_wind_direction", sa.Float(), nullable=True),
        sa.Column("reading_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["growing_area_id"], ["growing_areas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("growing_area_id", "week_start", name="uq_weekly_summary_area_week"),
    )
    op.create_index(
        "ix_weekly_summaries_area_week_start",
        "weekly_sensor_summaries",
        ["growing_area_id", "week_start"],
    )


def downgrade() -> None:
    op.drop_index("ix_weekly_summaries_area_week_start", table_name="weekly_sensor_summaries")
    op.drop_table("weekly_sensor_summaries")

    op.alter_column(
        "sensor_readings",
        "wind_direction",
        existing_type=sa.Float(),
        type_=sa.String(length=3),
        existing_nullable=True,
        postgresql_using="NULL::varchar(3)",
    )
