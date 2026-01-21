"""restored: delete profiles

Revision ID: 56590feb6ad7
Revises: 35970bec632a
Create Date: 2026-01-19 22:29:37.309127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56590feb6ad7'
down_revision: Union[str, Sequence[str], None] = '35970bec632a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
