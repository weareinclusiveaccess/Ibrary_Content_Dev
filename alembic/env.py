"""Alembic environment configuration."""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure .env is loaded from project root when running from any cwd
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

from alembic import context
from sqlalchemy import engine_from_config, pool, text

sys.path.insert(0, str(_project_root / "src"))

from ibrary.config import DATABASE_URL, POSTGRES_SCHEMA  # noqa: E402
from ibrary.models import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata

# Keep Alembic's version table alongside app tables (see migration SCHEMA).
_ALEMBIC_KWARGS = {
    "target_metadata": target_metadata,
    "version_table_schema": POSTGRES_SCHEMA,
}


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, literal_binds=True, **_ALEMBIC_KWARGS)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Schema must exist before Alembic creates alembic_version there (first run).
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{POSTGRES_SCHEMA}"'))
        connection.commit()

        context.configure(connection=connection, **_ALEMBIC_KWARGS)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
