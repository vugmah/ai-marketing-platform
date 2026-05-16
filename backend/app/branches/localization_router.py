"""Localization router."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.branches.localization_service import LocalizationService

router = APIRouter(prefix="/localization", tags=["Localization"])


class TranslationCreate(BaseModel):
    key: str
    language: str
    value: str
    module: str = "general"


class BranchLocaleUpdate(BaseModel):
    language: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    date_format: Optional[str] = None


@router.get("/translate/{key}")
async def translate(
    key: str,
    language: str = "tr",
    module: str = "general",
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = LocalizationService(db)
    value = await svc.get_translation(key, language, module)
    return {"key": key, "language": language, "value": value}


@router.post("/translate")
async def set_translation(
    req: TranslationCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = LocalizationService(db)
    t = await svc.set_translation(req.key, req.language, req.value, req.module)
    return {"translation": t}


@router.get("/branch-locale/{branch_id}")
async def get_branch_locale(
    branch_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = LocalizationService(db)
    locale = await svc.get_branch_locale(branch_id)
    return {"locale": locale}


@router.post("/branch-locale/{branch_id}")
async def set_branch_locale(
    branch_id: int,
    req: BranchLocaleUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = LocalizationService(db)
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    locale = await svc.set_branch_locale(current_user.company_id, branch_id, **data)
    return {"locale": locale}


@router.get("/format/currency")
async def format_currency(
    amount: float,
    currency: str = "TRY",
    locale: str = "tr",
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    svc = LocalizationService(db)
    formatted = await svc.format_currency(amount, currency, locale)
    return {"formatted": formatted}
