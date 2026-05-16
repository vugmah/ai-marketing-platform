"""Localization service."""

from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.branches.localization_models import (
    LocalizationString,
    BranchLocaleSettings,
    AIPromptTemplate,
)


class LocalizationService:
    """Multi-language and localization service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_translation(self, key: str, language: str = "tr", module: str = "general") -> str:
        result = await self.db.execute(
            select(LocalizationString.value)
            .where(
                and_(
                    LocalizationString.key == key,
                    LocalizationString.language == language,
                    LocalizationString.module == module,
                )
            )
        )
        row = result.scalar_one_or_none()
        return row or key

    async def set_translation(
        self, key: str, language: str, value: str, module: str = "general"
    ) -> LocalizationString:
        result = await self.db.execute(
            select(LocalizationString).where(
                and_(
                    LocalizationString.key == key,
                    LocalizationString.language == language,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.module = module
        else:
            existing = LocalizationString(key=key, language=language, value=value, module=module)
            self.db.add(existing)
        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def get_branch_locale(self, branch_id: int) -> Optional[BranchLocaleSettings]:
        result = await self.db.execute(
            select(BranchLocaleSettings).where(BranchLocaleSettings.branch_id == branch_id)
        )
        return result.scalar_one_or_none()

    async def set_branch_locale(self, company_id: int, branch_id: int, **kwargs) -> BranchLocaleSettings:
        settings = await self.get_branch_locale(branch_id)
        if not settings:
            settings = BranchLocaleSettings(company_id=company_id, branch_id=branch_id, **kwargs)
            self.db.add(settings)
        else:
            for k, v in kwargs.items():
                if hasattr(settings, k):
                    setattr(settings, k, v)
        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    async def get_ai_prompt(self, template_key: str, language: str = "tr") -> Optional[AIPromptTemplate]:
        result = await self.db.execute(
            select(AIPromptTemplate).where(
                and_(
                    AIPromptTemplate.template_key == template_key,
                    AIPromptTemplate.language == language,
                )
            )
        )
        return result.scalar_one_or_none()

    async def format_currency(self, amount: float, currency: str = "TRY", locale: str = "tr") -> str:
        if locale == "tr":
            return f"{amount:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif locale == "en":
            return f"{currency} {amount:,.2f}"
        elif locale == "ru":
            return f"{amount:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", " ")
        return f"{amount} {currency}"

    async def format_datetime(self, dt, locale: str = "tr") -> str:
        if locale in ("tr", "az", "ru"):
            return dt.strftime("%d.%m.%Y %H:%M")
        return dt.strftime("%m/%d/%Y %I:%M %p")
