"""backfill plot_index and growing_area_plot_id on all tables

Revision ID: a4b5c6d7e8f9
Revises: e2f3a4b5c6d7
Create Date: 2026-06-13

1. Assign plot_index to existing growing_area_plots rows (1-based per area by created_at).
2. Insert plot_index=0 sentinel for every growing_area that doesn't already have one.
3. Backfill crop_cycles.growing_area_plot_id where null → sentinel for area.
4. Backfill sensor_readings.growing_area_plot_id → sentinel for area.
5. Backfill alerts.growing_area_plot_id → sentinel for area.
"""

from alembic import op

revision = "a4b5c6d7e8f9"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: number existing plots 1-based per area ordered by created_at
    op.execute("""
        UPDATE growing_area_plots gap
        SET plot_index = sub.rn
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY growing_area_id ORDER BY created_at
                   ) AS rn
            FROM growing_area_plots
            WHERE plot_index IS NULL
        ) sub
        WHERE gap.id = sub.id
    """)

    # Step 2: insert plot_index=0 sentinel for every growing_area lacking one.
    # plot_type is NOT NULL: open_field areas get trial_strip; greenhouses get dwc_row.
    op.execute("""
        INSERT INTO growing_area_plots
            (id, growing_area_id, owner_id, plot_index, plot_type, is_active, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            ga.id,
            ga.owner_id,
            0,
            CASE ga.area_type
                WHEN 'open_field' THEN 'trial_strip'::plottype
                ELSE 'dwc_row'::plottype
            END,
            true,
            now(),
            now()
        FROM growing_areas ga
        WHERE NOT EXISTS (
            SELECT 1 FROM growing_area_plots
            WHERE growing_area_id = ga.id AND plot_index = 0
        )
    """)

    # Step 3: backfill crop_cycles.growing_area_plot_id where null (use sentinel)
    op.execute("""
        UPDATE crop_cycles cc
        SET growing_area_plot_id = gap.id
        FROM growing_area_plots gap
        WHERE gap.growing_area_id = cc.growing_area_id
          AND gap.plot_index = 0
          AND cc.growing_area_plot_id IS NULL
    """)

    # Step 4: backfill sensor_readings.growing_area_plot_id (all rows)
    op.execute("""
        UPDATE sensor_readings sr
        SET growing_area_plot_id = gap.id
        FROM growing_area_plots gap
        WHERE gap.growing_area_id = sr.growing_area_id
          AND gap.plot_index = 0
    """)

    # Step 5: backfill alerts.growing_area_plot_id (all rows)
    op.execute("""
        UPDATE alerts al
        SET growing_area_plot_id = gap.id
        FROM growing_area_plots gap
        WHERE gap.growing_area_id = al.growing_area_id
          AND gap.plot_index = 0
    """)


def downgrade() -> None:
    op.execute("UPDATE sensor_readings SET growing_area_plot_id = NULL")
    op.execute("UPDATE alerts SET growing_area_plot_id = NULL")
    op.execute("UPDATE crop_cycles SET growing_area_plot_id = NULL")
    op.execute("DELETE FROM growing_area_plots WHERE plot_index = 0")
    op.execute("UPDATE growing_area_plots SET plot_index = NULL")
