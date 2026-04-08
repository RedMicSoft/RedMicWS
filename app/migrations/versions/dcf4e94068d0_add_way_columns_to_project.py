"""Add way columns to Project

Revision ID: dcf4e94068d0
Revises: 81ca6b47d5f2
Create Date: 2026-04-08 14:18:46.653471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcf4e94068d0'
down_revision: Union[str, Sequence[str], None] = '81ca6b47d5f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('way', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'way')
