"""enforce growing_area_plot_id NOT NULL and add unique index on plot_index

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-06-13

After backfill, enforce NOT NULL on growing_area_plot_id across all three tables
and enforce NOT NULL + UNIQUE on growing_area_plots.plot_index.
Also changes crop_cycles FK from SET NULL to RESTRICT now that the column is NOT NULL.
"""

from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enforce NOT NULL on all three tables
    op.execute("ALTER TABLE crop_cycles ALTER COLUMN growing_area_plot_id SET NOT NULL")
    op.execute("ALTER TABLE sensor_readings ALTER COLUMN growing_area_plot_id SET NOT NULL")
    op.execute("ALTER TABLE alerts ALTER COLUMN growing_area_plot_id SET NOT NULL")

    # Change crop_cycles FK ondelete from SET NULL to RESTRICT
    op.execute(
        "ALTER TABLE crop_cycles "
        "DROP CONSTRAINT IF EXISTS crop_cycles_growing_area_plot_id_fkey"
    )
    op.execute(
        "ALTER TABLE crop_cycles "
        "ADD CONSTRAINT crop_cycles_growing_area_plot_id_fkey "
        "FOREIGN KEY (growing_area_plot_id) REFERENCES growing_area_plots(id)"
    )

    # Enforce NOT NULL + UNIQUE on plot_index
    op.execute("ALTER TABLE growing_area_plots ALTER COLUMN plot_index SET NOT NULL")
    op.create_unique_constraint(
        "uq_growing_area_plots_area_plot_index",
        "growing_area_plots",
        ["growing_area_id", "plot_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_growing_area_plots_area_plot_index", "growing_area_plots", type_="unique"
    )
    op.execute("ALTER TABLE growing_area_plots ALTER COLUMN plot_index DROP NOT NULL")

    op.execute(
        "ALTER TABLE crop_cycles "
        "DROP CONSTRAINT IF EXISTS crop_cycles_growing_area_plot_id_fkey"
    )
    op.execute(
        "ALTER TABLE crop_cycles "
        "ADD CONSTRAINT crop_cycles_growing_area_plot_id_fkey "
        "FOREIGN KEY (growing_area_plot_id) REFERENCES growing_area_plots(id) ON DELETE SET NULL"
    )

    op.execute("ALTER TABLE alerts ALTER COLUMN growing_area_plot_id DROP NOT NULL")
    op.execute("ALTER TABLE sensor_readings ALTER COLUMN growing_area_plot_id DROP NOT NULL")
    op.execute("ALTER TABLE crop_cycles ALTER COLUMN growing_area_plot_id DROP NOT NULL")
