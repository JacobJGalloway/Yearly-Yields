"""add transplanted crop cycle status

Revision ID: c4e3d2f1a0b9
Revises: a217e01e6086
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4e3d2f1a0b9'
down_revision: Union[str, None] = 'a217e01e6086'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE cropcyclestatus ADD VALUE IF NOT EXISTS 'transplanted'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # To roll back: create a replacement type without 'transplanted',
    # migrate all rows, drop the old type, and rename the new one.
    pass
