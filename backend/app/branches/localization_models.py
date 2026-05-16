"""Multi-language & localization models."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class LocalizationString(Base):
    """Translation string store."""
    __tablename__ = "localization_strings"
    __table_args__ = (
        Index("ix_ls_key_lang", "key", "language"),
        Index("ix_ls_module", "module"),
        {"schema": "public", "comment": "Translation strings per language"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(200), nullable=False)
    language = Column(String(5), nullable=False)  # tr, az, en, ru
    value = Column(String(2000), nullable=False)
    module = Column(String(50), nullable=False, default="general")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BranchLocaleSettings(Base):
    """Per-branch locale and timezone settings."""
    __tablename__ = "branch_locale_settings"
    __table_args__ = (
        Index("ix_bls_branch", "branch_id", unique=True),
        {"schema": "public", "comment": "Branch locale, timezone, currency settings"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False, index=True)
    language = Column(String(5), nullable=False, default="tr")
    timezone = Column(String(100), nullable=False, default="Europe/Istanbul")
    currency = Column(String(3), nullable=False, default="TRY")
    date_format = Column(String(20), nullable=False, default="%d.%m.%Y")
    time_format = Column(String(20), nullable=False, default="%H:%M")
    number_format_decimal = Column(String(1), nullable=False, default=",")
    number_format_thousand = Column(String(1), nullable=False, default=".")
    first_day_of_week = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class AIPromptTemplate(Base):
    """Multilingual AI prompt templates."""
    __tablename__ = "ai_prompt_templates"
    __table_args__ = (
        Index("ix_apt_key_lang", "template_key", "language"),
        {"schema": "public", "comment": "Multilingual AI prompt templates"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_key = Column(String(100), nullable=False)
    language = Column(String(5), nullable=False, default="tr")
    system_prompt = Column(String(4000), nullable=False)
    user_prompt_template = Column(String(4000), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
