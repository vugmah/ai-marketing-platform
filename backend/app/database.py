"""SQLAlchemy 2.0 async database setup.

Includes SoftDeleteMixin for GDPR/KVKK compliant data governance.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)


# =============================================================================
# Railway MySQL Fix - Bypass pydantic settings, read env vars directly
# =============================================================================

def _get_database_url() -> str:
    """Build database URL from Railway environment variables.

    Order of precedence:
    1. DATABASE_URL env var (Railway auto-provides this for MySQL addon)
    2. MYSQL_URL env var
    3. Individual Railway MySQL env vars (MYSQLHOST, MYSQLPORT, etc.)
    4. Fallback to SQLite (for local dev only)

    IMPORTANT: If DATABASE_URL contains 'localhost', it means Railway
    MySQL addon env var is stale. Use individual MYSQLHOST instead.
    """
    # 3. Individual Railway MySQL env vars (CHECK FIRST - Railway DATABASE_URL is stale)
    host = os.environ.get("MYSQLHOST", "")
    if host and host != "localhost":
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "")
        password = os.environ.get("MYSQLPASSWORD", "")
        database = os.environ.get("MYSQLDATABASE", "")
        if user and password and database:
            db_url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
            logger.warning(f"[DB] Using individual MYSQLHOST env var: {host}")
            return db_url

    # 1. DATABASE_URL (Railway sets this when MySQL addon is connected)
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and "localhost" not in db_url:
        # Convert sync mysql:// to async mysql+aiomysql://
        if db_url.startswith("mysql://") and not db_url.startswith("mysql+aiomysql://"):
            db_url = db_url.replace("mysql://", "mysql+aiomysql://", 1)
        return db_url
    elif db_url and "localhost" in db_url:
        logger.warning(f"[DB] DATABASE_URL has localhost, ignoring: {db_url[:40]}...")

    # 2. MYSQL_URL
    mysql_url = os.environ.get("MYSQL_URL", "")
    if mysql_url and "localhost" not in mysql_url:
        if mysql_url.startswith("mysql://") and not mysql_url.startswith("mysql+aiomysql://"):
            mysql_url = mysql_url.replace("mysql://", "mysql+aiomysql://", 1)
        return mysql_url

    # 4. Fallback to SQLite (local dev)
    logger.warning("[DB] No Railway MySQL env vars found, using SQLite fallback")
    return "sqlite+aiosqlite:///./aimarketing.db"


# Get DB URL at module load time
DATABASE_URL = _get_database_url()

# Debug: log DB URL with masked password
if DATABASE_URL:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(DATABASE_URL)
        masked_url = DATABASE_URL.replace(f":{parsed.password}@", ":****@") if parsed.password else DATABASE_URL
    except Exception:
        masked_url = DATABASE_URL
    logger.warning(f"[DB] Database URL: {masked_url}")
else:
    logger.error("[DB] No DATABASE_URL configured!")

# SQLite doesn't support pool_size/max_overflow
_is_sqlite = "sqlite" in DATABASE_URL.lower()
_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if not _is_sqlite:
    _engine_kwargs.update(pool_size=20, max_overflow=30)

engine = create_async_engine(
    DATABASE_URL,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


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


# Alias for backward compatibility (media/router.py uses get_db_session)
get_db_session = get_db


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


# =============================================================================
# Soft Delete Mixin & Query Helpers (GDPR/KVKK Compliance)
# =============================================================================


class SoftDeleteMixin:
    """Mixin that adds soft-delete columns to any SQLAlchemy model.

    Use this mixin for tables that need GDPR/KVKK-compliant deletion
    where records must be retained for a period before hard deletion.

    Attributes:
        deleted_at: Timestamp when the record was soft-deleted.
        deleted_by: FK to the user who performed the soft delete.
        is_deleted: Flag indicating whether the record is soft-deleted.
    """

    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL", name="fk_deleted_by_user_id"),
        nullable=True,
    )
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    def soft_delete(self, deleted_by: int | None = None) -> None:
        """Mark this record as soft-deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class ArchiveMixin(SoftDeleteMixin):
    """Extended mixin that adds archiving fields for company/branch-level archiving.

    When a company or branch is archived, all related entities get
    `archived_at` and `archived_by` set via cascade.
    """

    archived_at = Column(DateTime, nullable=True, index=True)
    archived_by = Column(
        Integer,
        ForeignKey("public.users.id", ondelete="SET NULL", name="fk_archived_by_user_id"),
        nullable=True,
    )
    is_archived = Column(Boolean, default=False, nullable=False, index=True)

    def archive(self, archived_by: int | None = None) -> None:
        """Mark this record as archived."""
        self.is_archived = True
        self.is_deleted = True
        self.archived_at = datetime.utcnow()
        self.archived_by = archived_by
        self.deleted_at = datetime.utcnow()
        self.deleted_by = archived_by

    def unarchive(self) -> None:
        """Restore an archived record."""
        self.is_archived = False
        self.is_deleted = False
        self.archived_at = None
        self.archived_by = None
        self.deleted_at = None
        self.deleted_by = None


def filter_not_deleted(query, model):
    """Apply soft-delete filter to a query if the model supports it.

    Args:
        query: SQLAlchemy select/query object.
        model: The SQLAlchemy model class to check for soft-delete columns.

    Returns:
        Query with is_deleted == False filter applied if the model
        has the SoftDeleteMixin, otherwise the original query.
    """
    if hasattr(model, "is_deleted"):
        return query.where(model.is_deleted.is_(False))
    return query


def filter_not_archived(query, model):
    """Apply archive filter to a query if the model supports it.

    Args:
        query: SQLAlchemy select/query object.
        model: The SQLAlchemy model class to check for archive columns.

    Returns:
        Query with is_archived == False filter applied if the model
        has the ArchiveMixin, otherwise the original query.
    """
    if hasattr(model, "is_archived"):
        return query.where(model.is_archived.is_(False))
    return query
