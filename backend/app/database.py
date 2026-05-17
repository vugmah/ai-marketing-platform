"""SQLAlchemy 2.0 async database setup."""

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
# Railway MySQL Fix
# =============================================================================

def _get_database_url() -> str:
    host = os.environ.get("MYSQLHOST", "")
    if host and host != "localhost":
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "")
        password = os.environ.get("MYSQLPASSWORD", "")
        database = os.environ.get("MYSQLDATABASE", "")
        if user and password and database:
            return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and "localhost" not in db_url:
        if db_url.startswith("mysql://") and not db_url.startswith("mysql+aiomysql://"):
            db_url = db_url.replace("mysql://", "mysql+aiomysql://", 1)
        return db_url

    mysql_url = os.environ.get("MYSQL_URL", "")
    if mysql_url and "localhost" not in mysql_url:
        if mysql_url.startswith("mysql://") and not mysql_url.startswith("mysql+aiomysql://"):
            mysql_url = mysql_url.replace("mysql://", "mysql+aiomysql://", 1)
        return mysql_url

    logger.warning("[DB] Using SQLite fallback")
    return "sqlite+aiosqlite:///./aimarketing.db"


DATABASE_URL = _get_database_url()

_is_sqlite = "sqlite" in DATABASE_URL.lower()
_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "pool_recycle": 3600,  # Recycle connections after 1 hour
}
if not _is_sqlite:
    _engine_kwargs.update(pool_size=20, max_overflow=30)

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


get_db_session = get_db
get_async_session = get_db


@asynccontextmanager
async def get_db_context() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables. FK errors from ai models are silently ignored."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        logger.info(f"[DB] Tables OK")
    except Exception as e:
        logger.debug(f"[DB] init: {type(e).__name__}")


async def close_db() -> None:
    await engine.dispose()


# =============================================================================
# Mixins
# =============================================================================

class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(Integer, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    def soft_delete(self, deleted_by=None):
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class ArchiveMixin(SoftDeleteMixin):
    archived_at = Column(DateTime, nullable=True, index=True)
    archived_by = Column(Integer, nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)

    def archive(self, archived_by=None):
        self.is_archived = True
        self.is_deleted = True
        self.archived_at = datetime.utcnow()
        self.archived_by = archived_by
        self.deleted_at = datetime.utcnow()
        self.deleted_by = archived_by

    def unarchive(self):
        self.is_archived = False
        self.is_deleted = False
        self.archived_at = None
        self.archived_by = None
        self.deleted_at = None
        self.deleted_by = None
