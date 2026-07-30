import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the `app` package importable when alembic is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402 (imports every model so metadata is complete)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate target: every table defined under app/models/.
target_metadata = Base.metadata

# Always use the real app configuration (env vars / .env) for the DB URL
# rather than whatever is hardcoded in alembic.ini. The app itself runs on
# asyncpg for runtime speed, but migrations don't benefit from async at
# all, and running them synchronously via psycopg2 avoids asyncio/asyncpg
# entirely for this one code path (simpler, and sidesteps any asyncio
# event-loop/driver quirks on the machine running `alembic upgrade`).
#
# Unlike app/db/postgres.py, nothing needs stripping out of the URL here:
# psycopg2 (via libpq) understands "sslmode" and "channel_binding" query
# params natively, so a Neon connection string pasted straight into
# DATABASE_URL works as-is -- only the driver/scheme prefix needs fixing.
raw_url = get_settings().database_url
if not raw_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Paste your Neon connection string into "
        ".env as DATABASE_URL (see .env.example) before running alembic."
    )
if raw_url.startswith("postgres://"):
    raw_url = "postgresql://" + raw_url[len("postgres://") :]
sync_url = raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
if sync_url.startswith("postgresql://"):
    sync_url = "postgresql+psycopg2://" + sync_url[len("postgresql://") :]
config.set_main_option("sqlalchemy.url", sync_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Plain synchronous engine/connection — no asyncio, no asyncpg. Alembic
    only needs a connection open for the duration of the migration, so the
    extra complexity (and Windows event-loop sensitivity) of an async
    engine buys nothing here.
    """

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()