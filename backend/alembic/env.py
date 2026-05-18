"""
Alembic async environment configuration.
Supports offline and online migration modes with SQLAlchemy 2.0 async engine.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import Connection

from alembic import context

import sys

sys.path.insert(0, "/app")

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402

# Import all models so Base.metadata contains all tables
from app.auth.models import User  # noqa: E402, F401
from app.companies.models import Company  # noqa: E402, F401
from app.branches.models import (  # noqa: E402, F401
    Branch,
    BranchConfig,
    ERPConnectionConfig,
    SocialAccountConfig,
    AIPromptOverride,
)
from app.erp.models import (  # noqa: E402, F401
    ERPConnection,
    ERPCustomer,
    ERPFieldMapping,
    ERPInventory,
    ERPInvoice,
    ERPPayment,
    ERPProduct,
    ERPSalesOrder,
    ERPSyncJob,
    ERPSyncLog,
)
from app.ads.models import *  # noqa: E402, F401
from app.ai.models import *  # noqa: E402, F401
from app.analytics.models import *  # noqa: E402, F401
from app.audit.models import *  # noqa: E402, F401
from app.billing.models import *  # noqa: E402, F401
from app.events.models import *  # noqa: E402, F401
from app.followers.models import *  # noqa: E402, F401
from app.governance.models import *  # noqa: E402, F401
from app.knowledge.models import *  # noqa: E402, F401
from app.media.models import *  # noqa: E402, F401
from app.reports.models import *  # noqa: E402, F401
from app.social.models import *  # noqa: E402, F401
from app.support.models import *  # noqa: E402, F401

# -- Alembic Config object --
config = context.config

# -- Logging --
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -- Target Metadata --
target_metadata = Base.metadata

# -- Database URL --
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Synchronous migration runner called via connection.run_sync().
    """
    # MySQL compatibility: no schema support
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL", "")
    is_mysql = url.startswith("mysql")

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=not is_mysql,
        version_table_schema=None if is_mysql else "public",
        render_as_batch=True,  # Required for MySQL compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.
    """
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# -- Entry point --
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
