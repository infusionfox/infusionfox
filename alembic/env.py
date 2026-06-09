# Make the project root importable so we can pick up our models and DB URL.
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.models import Base
from app.db.session import DB_URL

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the URL from alembic.ini with whatever the app actually uses.
# This makes alembic and the app agree, regardless of INFUSIONFOX_DB_URL.
config.set_main_option("sqlalchemy.url", DB_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at our SQLAlchemy metadata for autogenerate.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# Names of tables / virtual tables we manage outside of SQLAlchemy ORM
# metadata. The search FTS5 virtual table generates several shadow
# tables that Alembic autogenerate would otherwise flag as "drift"
# because they're not in Base.metadata. Exclude them from the diff.
_NON_ORM_TABLE_PREFIXES = ("search_index",)


def _include_name(name, type_, parent_names):
    """Tell Alembic's autogenerate to skip FTS5 shadow tables."""
    if type_ == "table":
        # `search_index`, `search_index_data`, `search_index_idx`, etc.
        for prefix in _NON_ORM_TABLE_PREFIXES:
            if name == prefix or name.startswith(prefix + "_"):
                return False
    return True


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
        render_as_batch=url.startswith("sqlite"),
        include_name=_include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
            include_name=_include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
