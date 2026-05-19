"""SQLAlchemy 2.0 async database setup."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, select, text
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
    """Build database URL from Railway env vars with extensive debug logging."""
    logger.info("[DB] Resolving database URL from environment...")

    # List all DB-related env vars for debugging (hide passwords)
    db_env_vars = {k: v for k, v in os.environ.items()
                   if any(x in k.upper() for x in ["DATABASE", "MYSQL", "DB"])}
    safe_env = {k: (v[:20] + "..." if len(v) > 20 else v) if "PASS" in k or "SECRET" in k else v
                for k, v in db_env_vars.items()}
    logger.info(f"[DB] Found env vars: {safe_env}")

    # Priority 1: Railway individual MySQL env vars (MYSQLHOST, MYSQLUSER, etc.)
    host = os.environ.get("MYSQLHOST", "")
    if host:
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "")
        password = os.environ.get("MYSQLPASSWORD", "")
        database = os.environ.get("MYSQLDATABASE", "")
        logger.info(f"[DB] Railway MySQL vars: host={host}, port={port}, user={user}, database={database}")
        if user and password and database:
            url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
            logger.info(f"[DB] Using Railway MySQL individual vars: {url.replace(password, '***')}")
            return url
        else:
            logger.warning(f"[DB] Railway MySQL vars incomplete: user={bool(user)}, pass={bool(password)}, db={bool(database)}")
    else:
        logger.info("[DB] MYSQLHOST not set, skipping individual vars")

    # Priority 2: Railway DATABASE_URL
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        logger.info(f"[DB] DATABASE_URL found: {db_url[:50]}...")
        # Convert mysql:// to mysql+aiomysql:// for async SQLAlchemy
        if db_url.startswith("mysql://") and not db_url.startswith("mysql+aiomysql://"):
            db_url = db_url.replace("mysql://", "mysql+aiomysql://", 1)
            logger.info("[DB] Converted mysql:// to mysql+aiomysql://")
        # Also handle postgres:// URLs from Railway
        if db_url.startswith("postgres://") and not db_url.startswith("postgresql+"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            logger.info("[DB] Converted postgres:// to postgresql+asyncpg://")
        logger.info(f"[DB] Using DATABASE_URL")
        return db_url
    else:
        logger.info("[DB] DATABASE_URL not set")

    # Priority 3: Railway MYSQL_URL
    mysql_url = os.environ.get("MYSQL_URL", "")
    if mysql_url:
        logger.info(f"[DB] MYSQL_URL found: {mysql_url[:50]}...")
        if mysql_url.startswith("mysql://") and not mysql_url.startswith("mysql+aiomysql://"):
            mysql_url = mysql_url.replace("mysql://", "mysql+aiomysql://", 1)
        logger.info("[DB] Using MYSQL_URL")
        return mysql_url
    else:
        logger.info("[DB] MYSQL_URL not set")

    # Priority 4: PGHOST for PostgreSQL
    pg_host = os.environ.get("PGHOST", "")
    if pg_host:
        pg_port = os.environ.get("PGPORT", "5432")
        pg_user = os.environ.get("PGUSER", "")
        pg_pass = os.environ.get("PGPASSWORD", "")
        pg_db = os.environ.get("PGDATABASE", "")
        if pg_user and pg_pass and pg_db:
            url = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
            logger.info(f"[DB] Using PostgreSQL vars")
            return url

    # Fallback: SQLite (for local dev only)
    logger.warning("[DB] No database env vars found. Using SQLite fallback (NOT for production)")
    return "sqlite+aiosqlite:///./aimarketing.db"


DATABASE_URL = _get_database_url()
logger.info(f"[DB] Final DATABASE_URL starts with: {DATABASE_URL.split('://')[0] if '://' in DATABASE_URL else 'unknown'}://")

_is_sqlite = "sqlite" in DATABASE_URL.lower()
_engine_kwargs = {
    "echo": False,
    # "pool_pre_ping": True,  # aiomysql uyumsuzluğu səbəbindən söndürüldü
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
    """Initialize database: connection check only in staging/prod;
    create_all only in local/dev. Alembic is the source of truth."""
    env = os.environ.get("ENVIRONMENT", "development").lower()

    if env in ("staging", "production"):
        # Staging/prod: create_all AÇIQ (geçici - cədvəllər yoxdursa yaradılsın)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all, checkfirst=True)
            logger.info(f"[DB] Tables OK (create_all in {env}; checkfirst=True)")
        except Exception as e:
            logger.exception(f"[DB] init failed: {type(e).__name__}: {e}")
    else:
        # Local/dev: create_all açık (hızlı prototyping)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all, checkfirst=True)
            logger.info(f"[DB] Tables OK (create_all in {env})")
        except Exception as e:
            logger.exception(f"[DB] init failed: {type(e).__name__}: {e}")


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
