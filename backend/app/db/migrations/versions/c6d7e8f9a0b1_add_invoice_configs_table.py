"""add invoice_configs table

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-06-13

Stores configurable default customer assignments per growing area for invoice
auto-generation. Seeded via POST /api/v1/admin/seed.
"""

from alembic import op
import sqlalchemy as sa

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("growing_area_id", sa.Uuid(), nullable=False),
        sa.Column("harvest_customer_id", sa.Uuid(), nullable=True),
        sa.Column("transplant_customer_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["growing_area_id"], ["growing_areas.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["harvest_customer_id"], ["customers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["transplant_customer_id"], ["customers.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("growing_area_id", name="uq_invoice_configs_growing_area"),
    )
    op.create_index(
        "ix_invoice_configs_growing_area_id",
        "invoice_configs",
        ["growing_area_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_configs_growing_area_id", table_name="invoice_configs")
    op.drop_table("invoice_configs")
