"""add_fiot_reading_source

Revision ID: ca974954e4a4
Revises: f2041dd1af15
Create Date: 2026-04-17 10:56:26.667987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca974954e4a4'
down_revision: Union[str, None] = 'f2041dd1af15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE readingsource ADD VALUE IF NOT EXISTS 'fiot'")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing enum values
