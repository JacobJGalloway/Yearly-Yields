"""update invoices table for v1.2

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-06-13

- Add invoice_type (harvest/transplant), description, sent_at, paid_at, voided_at.
- Rename rate_id → crop_rate_id.
- Make customer_id, crop_rate_id, unit_price, total_amount nullable to support
  invoices created before a customer or CropRate is configured.
"""

from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "invoices",
        sa.Column(
            "invoice_type",
            sa.String(length=20),
            nullable=False,
            server_default="harvest",
        ),
    )
    op.add_column("invoices", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Rename rate_id → crop_rate_id (drop old FK, rename, recreate FK)
    op.execute(
        "ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_rate_id_fkey"
    )
    op.execute("ALTER TABLE invoices RENAME COLUMN rate_id TO crop_rate_id")
    op.execute(
        "ALTER TABLE invoices "
        "ADD CONSTRAINT invoices_crop_rate_id_fkey "
        "FOREIGN KEY (crop_rate_id) REFERENCES crop_rates(id)"
    )

    # Make columns nullable
    op.alter_column("invoices", "customer_id", nullable=True)
    op.alter_column("invoices", "crop_rate_id", nullable=True)
    op.alter_column("invoices", "unit_price", nullable=True)
    op.alter_column("invoices", "total_amount", nullable=True)

    # Drop the server_default now that existing rows are backfilled
    op.alter_column("invoices", "invoice_type", server_default=None)


def downgrade() -> None:
    op.alter_column("invoices", "total_amount", nullable=False)
    op.alter_column("invoices", "unit_price", nullable=False)
    op.alter_column("invoices", "crop_rate_id", nullable=False)
    op.alter_column("invoices", "customer_id", nullable=False)

    op.execute(
        "ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_crop_rate_id_fkey"
    )
    op.execute("ALTER TABLE invoices RENAME COLUMN crop_rate_id TO rate_id")
    op.execute(
        "ALTER TABLE invoices "
        "ADD CONSTRAINT invoices_rate_id_fkey "
        "FOREIGN KEY (rate_id) REFERENCES crop_rates(id)"
    )

    op.drop_column("invoices", "voided_at")
    op.drop_column("invoices", "paid_at")
    op.drop_column("invoices", "sent_at")
    op.drop_column("invoices", "description")
    op.drop_column("invoices", "invoice_type")
