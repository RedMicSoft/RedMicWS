import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.database import Base
import os
from dotenv import load_dotenv

load_dotenv()

# Импорт всех моделей (у тебя уже есть)
from app.files.models import FileModel
from app.links.models import Link
from app.roles.models import Role, RoleSeries, RoleHistory
from app.projects.models import Project, ProjectLink, ProjectUser
from app.series.models import Series
from app.users.models import User, Contacts
from app.levels.models import Level, UserLevel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,  # ← Сравнивать типы колонок
        compare_server_default=True,  # ← КРИТИЧЕСКИ ВАЖНО для server_default!
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # ⚠️ ДОБАВЬ эти настройки!
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # ←
        compare_server_default=True,  # ←
        compare_default=True,  # ← Для default значений
        compare_nullable=True,  # ← Для nullable
        include_schemas=True,  # ← Если используешь схемы
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


db_url = os.getenv("DB_URL")

if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
