"""add series_id to ass_fixes

Revision ID: a1b2c3d4e5f6
Revises: dcf4e94068d0
Create Date: 2026-04-08 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "dcf4e94068d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ass_fixes", sa.Column("series_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "ass_fixes_series_id_fkey",
        "ass_fixes",
        "series",
        ["series_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("ass_fixes_series_id_fkey", "ass_fixes", type_="foreignkey")
    op.drop_column("ass_fixes", "series_id")
