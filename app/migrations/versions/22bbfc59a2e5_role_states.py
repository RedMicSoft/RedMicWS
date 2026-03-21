"""Role states

Revision ID: 22bbfc59a2e5
Revises: 50cad6d09677
Create Date: 2026-03-21 16:22:17.590269

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "22bbfc59a2e5"
down_revision: Union[str, Sequence[str], None] = "50cad6d09677"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    role_state_enum = sa.Enum(
        "не загружена",
        "не затаймлена",
        "не проверена",
        "требуются фиксы",
        "готова к сведению",
        name="rolestate",
    )
    role_state_enum.create(op.get_bind(), checkfirst=True)

    # 2. Теперь меняем тип колонки.
    # Добавляем postgresql_using, чтобы база знала, как конвертировать старые строки в новый тип
    op.alter_column(
        "roles",
        "state",
        existing_type=sa.VARCHAR(),
        type_=role_state_enum,
        postgresql_using="state::rolestate",
        existing_nullable=False,
    )


def downgrade() -> None:
    # 1. Сначала возвращаем тип колонки к VARCHAR
    op.alter_column(
        "roles",
        "state",
        existing_type=sa.Enum(name="rolestate"),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )

    # 2. Удаляем сам тип ENUM из базы данных
    sa.Enum(name="rolestate").drop(op.get_bind(), checkfirst=True)
