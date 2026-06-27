"""projects_users user_id cascade, drop default

Revision ID: de0cf84b5ec7
Revises: d295ace07bbb
Create Date: 2026-06-27 13:52:27.228323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "de0cf84b5ec7"
down_revision: Union[str, Sequence[str], None] = "d295ace07bbb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "projects_users",
        "user_id",
        existing_type=sa.INTEGER(),
        server_default=None,
        existing_nullable=False,
    )
    op.drop_constraint(
        "projects_users_user_id_fkey", "projects_users", type_="foreignkey"
    )
    op.create_foreign_key(
        None,
        "projects_users",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, "projects_users", type_="foreignkey")
    op.create_foreign_key(
        "projects_users_user_id_fkey",
        "projects_users",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="SET DEFAULT",
    )
    op.alter_column(
        "projects_users",
        "user_id",
        existing_type=sa.INTEGER(),
        server_default="-1",
        existing_nullable=False,
    )
