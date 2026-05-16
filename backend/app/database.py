"""SQLAlchemy 2.0 async database setup.

Includes SoftDeleteMixin for GDPR/KVKK compliant data governance.
"""

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

from app.config import settings

# Railway MySQL fix: try env var directly if settings.DATABASE_URL is empty
_raw_db_url = settings.DATABASE_URL or os.environ.get("DATABASE_URL", "")
# Also try Railway individual MySQL env vars
if not _raw_db_url:
    mysqlhost = os.environ.get("MYSQLHOST", "")
    if mysqlhost:
        mysqlport = os.environ.get("MYSQLPORT", "3306")
        mysqluser = os.environ.get("MYSQLUSER", "")
        mysqlpassword = os.environ.get("MYSQLPASSWORD", "")
        mysqldatabase = os.environ.get("MYSQLDATABASE", "")
        _raw_db_url = f"mysql+aiomysql://{mysqluser}:{mysqlpassword}@{mysqlhost}:{mysqlport}/{mysqldatabase}"

# Convert sync mysql:// to async mysql+aiomysql://
if _raw_db_url and _raw_db_url.startswith("mysql://") and not _raw_db_url.startswith("mysql+aiomysql://"):
    _raw_db_url = _raw_db_url.replace("mysql://", "mysql+aiomysql://", 1)

# Ensure we have a DB URL
if not _raw_db_url:
    _raw_db_url = "sqlite+aiosqlite:///./aimarketing.db"

# SQLite doesn't support pool_size/max_overflow
_is_sqlite = "sqlite" in _raw_db_url.lower()
_engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}
if not _is_sqlite:
    _engine_kwargs.update(pool_size=20, max_overflow=30)

engine = create_async_engine(
    _raw_db_url,
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
