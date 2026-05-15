"""SQLAlchemy 2.0 async database setup."""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()

# Import all models AFTER Base is defined to avoid circular imports
from app.auth.models import User  # noqa: F401, E402
from app.companies.models import Company  # noqa: F401, E402
from app.branches.models import Branch  # noqa: F401, E402
from app.erp.models import (  # noqa: F401, E402
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


async def get_db() -> AsyncSession:
    """Async generator yielding a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncSession:
    """Async context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the database engine."""
    await engine.dispose()
