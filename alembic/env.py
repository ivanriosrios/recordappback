from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

from app.core.config import get_settings
from app.core.database import Base

# Importar todos los modelos para que Alembic los detecte
from app.models import Business, Client, Service, Reminder, Template, ReminderLog  # noqa

config = context.config
settings = get_settings()

# Alembic usa psycopg2 (sync) — más estable para DDL que asyncpg.
# La app usa asyncpg en runtime, pero las migraciones corren con el driver sync.
_sync_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
).replace(
    "postgresql+asyncpg:", "postgresql+psycopg2:"
)
config.set_main_option("sqlalchemy.url", _sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
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
