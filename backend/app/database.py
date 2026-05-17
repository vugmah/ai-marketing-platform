"""SQLAlchemy 2.0 async database setup.

Includes SoftDeleteMixin for GDPR/KVKK compliant data governance.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, select, text as sa_text
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
    """Build database URL from Railway environment variables."""
    # 1. Railway individual MySQL env vars (CHECK FIRST)
    host = os.environ.get("MYSQLHOST", "")
    if host and host != "localhost":
        port = os.environ.get("MYSQLPORT", "3306")
        user = os.environ.get("MYSQLUSER", "")
        password = os.environ.get("MYSQLPASSWORD", "")
        database = os.environ.get("MYSQLDATABASE", "")
        if user and password and database:
            db_url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
            logger.info(f"[DB] Using individual MYSQLHOST: {host}")
            return db_url

    # 2. DATABASE_URL
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url and "localhost" not in db_url:
        if db_url.startswith("mysql://") and not db_url.startswith("mysql+aiomysql://"):
            db_url = db_url.replace("mysql://", "mysql+aiomysql://", 1)
        return db_url
    elif db_url and "localhost" in db_url:
        logger.warning(f"[DB] DATABASE_URL has localhost, ignoring")

    # 3. MYSQL_URL
    mysql_url = os.environ.get("MYSQL_URL", "")
    if mysql_url and "localhost" not in mysql_url:
        if mysql_url.startswith("mysql://") and not mysql_url.startswith("mysql+aiomysql://"):
            mysql_url = mysql_url.replace("mysql://", "mysql+aiomysql://", 1)
        return mysql_url

    # 4. Fallback to SQLite
    logger.warning("[DB] No Railway MySQL, using SQLite")
    return "sqlite+aiosqlite:///./aimarketing.db"


DATABASE_URL = _get_database_url()

_is_sqlite = "sqlite" in DATABASE_URL.lower()
_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if not _is_sqlite:
    _engine_kwargs.update(pool_size=20, max_overflow=30)

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
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


get_db_session = get_db
get_async_session = get_db


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
    """Create all database tables with FK-safe two-pass approach.

    Pass 1: Create tables without FK constraints (avoid NoReferencedTableError)
    Pass 2: Add FK constraints to existing tables
    """
    from sqlalchemy.schema import CreateTable, AddConstraint
    from sqlalchemy import ForeignKeyConstraint, CheckConstraint

    tables = list(Base.metadata.sorted_tables)
    logger.info(f"[DB] {len(tables)} tables in metadata")

    # Separate FK constraints from tables for deferred application
    fk_constraints = {}
    for table in tables:
        fks = [c for c in table.constraints if isinstance(c, ForeignKeyConstraint)]
        if fks:
            fk_constraints[table.name] = fks
            # Remove FKs from table for first pass
            for fk in fks:
                table.constraints.discard(fk)

    # Pass 1: Create tables without FKs
    created = 0
    for table in tables:
        try:
            async with engine.begin() as conn:
                await conn.execute(CreateTable(table, if_not_exists=True))
            created += 1
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.debug(f"[DB] Table '{table.name}' create: {type(e).__name__}")

    logger.info(f"[DB] Pass 1: {created}/{len(tables)} tables created")

    # Pass 2: Add FK constraints
    if fk_constraints and not _is_sqlite:
        fk_added = 0
        for table_name, fks in fk_constraints.items():
            table = Base.metadata.tables.get(table_name)
            if not table:
                continue
            for fk in fks:
                try:
                    async with engine.begin() as conn:
                        await conn.execute(AddConstraint(fk))
                    fk_added += 1
                except Exception as e:
                    logger.debug(f"[DB] FK on {table_name}: {type(e).__name__}")
        logger.info(f"[DB] Pass 2: {fk_added} FK constraints added")

    # Restore FK constraints to metadata for future use
    for table_name, fks in fk_constraints.items():
        table = Base.metadata.tables.get(table_name)
        if table:
            for fk in fks:
                table.constraints.add(fk)


async def close_db() -> None:
    """Dispose of the database engine."""
    await engine.dispose()


# =============================================================================
# Soft Delete Mixin & Query Helpers
# =============================================================================

class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(Integer, ForeignKey("users.id", name="fk_deleted_by"), nullable=True)
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
    archived_by = Column(Integer, ForeignKey("users.id", name="fk_archived_by"), nullable=True)
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
