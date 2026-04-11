"""add record_note to records

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("records", sa.Column("record_note", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("records", "record_note")
