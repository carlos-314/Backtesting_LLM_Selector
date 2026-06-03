"""Entorno Alembic — apunta a la BBDD propia y a Base de F2 §5.

La URL se deriva de `settings.APP_DATABASE_URL` quitando el driver async
(`+asyncpg`) porque Alembic ejecuta migraciones en modo sync.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.infrastructure.persistence.app_db import Base

# Importar los módulos que registran modelos en Base.metadata.
from app.infrastructure.persistence import models  # noqa: F401

config = context.config


def _sync_url(async_url: str) -> str:
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)


config.set_main_option("sqlalchemy.url", _sync_url(settings.APP_DATABASE_URL))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
