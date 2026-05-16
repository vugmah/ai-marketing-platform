"""Branches router with branch CRUD + branch config operations (real DB)."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.companies.models import Company
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import NotFoundError

from .models import (
    AIPromptOverride,
    Branch,
    BranchConfig,
    ERPConnectionConfig,
    SocialAccountConfig,
)
from .schemas import (
    AIPromptOverrideCreate,
    AIPromptOverrideResponse,
    AIPromptOverrideUpdate,
    BranchConfigCreate,
    BranchConfigResponse,
    BranchConfigUpdate,
    BranchCreate,
    BranchResponse,
    BranchUpdate,
    ERPConnectionConfigCreate,
    ERPConnectionConfigResponse,
    ERPConnectionConfigUpdate,
    SocialAccountConfigCreate,
    SocialAccountConfigResponse,
    SocialAccountConfigUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _require_company_access(
    company_id: int,
    current_user: User,
) -> None:
    """Raise NotFoundError if the user cannot access the given company."""
    if current_user.role == "super_admin":
        return
    if current_user.company_id != company_id:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")


async def _require_branch_access(
    branch: Branch,
    current_user: User,
) -> None:
    """Raise NotFoundError if the user cannot access the given branch."""
    if current_user.role == "super_admin":
        return
    if branch.company_id != current_user.company_id:
        raise NotFoundError(
            detail=f"Branch with ID {branch.id} not found"
        )


# ---------------------------------------------------------------------------
# Branch CRUD endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=list[BranchResponse],
    status_code=status.HTTP_200_OK,
    summary="List branches",
)
async def list_branches(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Branch]:
    """List branches with tenant isolation.

    * super_admin  -> all branches
    * other roles  -> branches within their company only
    """
    query = select(Branch)
    if current_user.role != "super_admin":
        query = query.where(Branch.company_id == current_user.company_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new branch",
)
async def create_branch(
    request: Request,
    data: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Branch:
    """Create a new branch within the user's company.

    * super_admin can create branches for any company
    * other roles can only create for their own company
    """
    # Tenant isolation: verify company access
    await _require_company_access(data.company_id, current_user)

    # Verify the target company exists
    company_result = await db.execute(
        select(Company).where(Company.id == data.company_id)
    )
    if company_result.scalar_one_or_none() is None:
        raise NotFoundError(
            detail=f"Company with ID {data.company_id} not found"
        )

    # Optional: enforce max_branches limit for non-super_admins
    if current_user.role != "super_admin":
        branch_count_result = await db.execute(
            select(func.count(Branch.id)).where(
                Branch.company_id == data.company_id
            )
        )
        branch_count = branch_count_result.scalar_one()

        company = company_result.scalar_one()
        if branch_count >= company.max_branches:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Branch limit reached ({company.max_branches}). "
                    "Upgrade your plan to add more branches."
                ),
            )

    branch = Branch(**data.model_dump())
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.get(
    "/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a branch by ID",
)
async def get_branch(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Branch:
    """Get a single branch with tenant isolation."""
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()

    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)
    return branch


@router.put(
    "/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a branch",
)
async def update_branch(
    branch_id: int,
    data: BranchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Branch:
    """Update a branch with tenant isolation."""
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()

    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    # Prevent changing company_id unless super_admin
    update_data = data.model_dump(exclude_unset=True)
    if "company_id" in update_data and current_user.role != "super_admin":
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can change a branch's company",
        )

    for field, value in update_data.items():
        setattr(branch, field, value)

    await db.commit()
    await db.refresh(branch)
    return branch


@router.delete(
    "/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a branch",
)
async def delete_branch(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a branch with tenant isolation."""
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()

    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    await db.delete(branch)
    await db.commit()


# ---------------------------------------------------------------------------
# Branch config (key-value store) endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{branch_id}/configs",
    response_model=list[BranchConfigResponse],
    status_code=status.HTTP_200_OK,
    summary="List configs for a branch",
)
async def list_branch_configs(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BranchConfig]:
    """List all config entries for a branch (tenant isolated)."""
    # Verify branch access first
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    config_result = await db.execute(
        select(BranchConfig).where(BranchConfig.branch_id == branch_id)
    )
    return config_result.scalars().all()


@router.post(
    "/{branch_id}/configs",
    response_model=BranchConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a config entry for a branch",
)
async def create_branch_config(
    branch_id: int,
    data: BranchConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchConfig:
    """Create a new config key-value pair for a branch."""
    # Verify branch access
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    config = BranchConfig(
        branch_id=branch_id,
        config_key=data.config_key,
        config_value=data.config_value,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.get(
    "/{branch_id}/configs/{config_id}",
    response_model=BranchConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single branch config",
)
async def get_branch_config(
    branch_id: int,
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchConfig:
    """Get a single branch config entry."""
    # Verify branch access
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    config_result = await db.execute(
        select(BranchConfig).where(
            BranchConfig.id == config_id,
            BranchConfig.branch_id == branch_id,
        )
    )
    config = config_result.scalar_one_or_none()
    if config is None:
        raise NotFoundError(
            detail=f"Config with ID {config_id} not found for branch {branch_id}"
        )
    return config


@router.put(
    "/{branch_id}/configs/{config_id}",
    response_model=BranchConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a branch config",
)
async def update_branch_config(
    branch_id: int,
    config_id: int,
    data: BranchConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchConfig:
    """Update a branch config value."""
    # Verify branch access
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    config_result = await db.execute(
        select(BranchConfig).where(
            BranchConfig.id == config_id,
            BranchConfig.branch_id == branch_id,
        )
    )
    config = config_result.scalar_one_or_none()
    if config is None:
        raise NotFoundError(
            detail=f"Config with ID {config_id} not found for branch {branch_id}"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return config


@router.delete(
    "/{branch_id}/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a branch config",
)
async def delete_branch_config(
    branch_id: int,
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a branch config entry."""
    # Verify branch access
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    config_result = await db.execute(
        select(BranchConfig).where(
            BranchConfig.id == config_id,
            BranchConfig.branch_id == branch_id,
        )
    )
    config = config_result.scalar_one_or_none()
    if config is None:
        raise NotFoundError(
            detail=f"Config with ID {config_id} not found for branch {branch_id}"
        )

    await db.delete(config)
    await db.commit()


# ---------------------------------------------------------------------------
# AI Prompt Override endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{branch_id}/ai-prompts",
    response_model=list[AIPromptOverrideResponse],
    status_code=status.HTTP_200_OK,
    summary="List AI prompt overrides for a branch",
)
async def list_ai_prompt_overrides(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AIPromptOverride]:
    """List all AI prompt overrides for a branch (tenant isolated)."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    prompt_result = await db.execute(
        select(AIPromptOverride).where(
            AIPromptOverride.branch_id == branch_id
        )
    )
    return prompt_result.scalars().all()


@router.post(
    "/{branch_id}/ai-prompts",
    response_model=AIPromptOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an AI prompt override for a branch",
)
async def create_ai_prompt_override(
    branch_id: int,
    data: AIPromptOverrideCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIPromptOverride:
    """Create a new AI prompt override for a branch."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    prompt = AIPromptOverride(
        branch_id=branch_id,
        prompt_key=data.prompt_key,
        prompt_template=data.prompt_template,
        is_active=data.is_active,
        priority=data.priority,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.get(
    "/{branch_id}/ai-prompts/{prompt_id}",
    response_model=AIPromptOverrideResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single AI prompt override",
)
async def get_ai_prompt_override(
    branch_id: int,
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIPromptOverride:
    """Get a single AI prompt override by ID."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    prompt_result = await db.execute(
        select(AIPromptOverride).where(
            AIPromptOverride.id == prompt_id,
            AIPromptOverride.branch_id == branch_id,
        )
    )
    prompt = prompt_result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundError(
            detail=f"AI prompt override with ID {prompt_id} not found for branch {branch_id}"
        )
    return prompt


@router.put(
    "/{branch_id}/ai-prompts/{prompt_id}",
    response_model=AIPromptOverrideResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an AI prompt override",
)
async def update_ai_prompt_override(
    branch_id: int,
    prompt_id: int,
    data: AIPromptOverrideUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIPromptOverride:
    """Update an AI prompt override."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    prompt_result = await db.execute(
        select(AIPromptOverride).where(
            AIPromptOverride.id == prompt_id,
            AIPromptOverride.branch_id == branch_id,
        )
    )
    prompt = prompt_result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundError(
            detail=f"AI prompt override with ID {prompt_id} not found for branch {branch_id}"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prompt, field, value)

    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete(
    "/{branch_id}/ai-prompts/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an AI prompt override",
)
async def delete_ai_prompt_override(
    branch_id: int,
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an AI prompt override."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    prompt_result = await db.execute(
        select(AIPromptOverride).where(
            AIPromptOverride.id == prompt_id,
            AIPromptOverride.branch_id == branch_id,
        )
    )
    prompt = prompt_result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundError(
            detail=f"AI prompt override with ID {prompt_id} not found for branch {branch_id}"
        )

    await db.delete(prompt)
    await db.commit()


# ---------------------------------------------------------------------------
# Social Account Config endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{branch_id}/social-accounts",
    response_model=list[SocialAccountConfigResponse],
    status_code=status.HTTP_200_OK,
    summary="List social account configs for a branch",
)
async def list_social_account_configs(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SocialAccountConfig]:
    """List all social account configs for a branch (tenant isolated)."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    social_result = await db.execute(
        select(SocialAccountConfig).where(
            SocialAccountConfig.branch_id == branch_id
        )
    )
    return social_result.scalars().all()


@router.post(
    "/{branch_id}/social-accounts",
    response_model=SocialAccountConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a social account config for a branch",
)
async def create_social_account_config(
    branch_id: int,
    data: SocialAccountConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SocialAccountConfig:
    """Create a new social account config for a branch."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    social = SocialAccountConfig(
        branch_id=branch_id,
        platform=data.platform,
        account_handle=data.account_handle,
        access_token=data.access_token,
        refresh_token=data.refresh_token,
        token_expires_at=data.token_expires_at,
        page_id=data.page_id,
        is_connected=data.is_connected,
        auto_publish=data.auto_publish,
        settings_json=data.settings_json,
    )
    db.add(social)
    await db.commit()
    await db.refresh(social)
    return social


@router.get(
    "/{branch_id}/social-accounts/{social_id}",
    response_model=SocialAccountConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single social account config",
)
async def get_social_account_config(
    branch_id: int,
    social_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SocialAccountConfig:
    """Get a single social account config by ID."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    social_result = await db.execute(
        select(SocialAccountConfig).where(
            SocialAccountConfig.id == social_id,
            SocialAccountConfig.branch_id == branch_id,
        )
    )
    social = social_result.scalar_one_or_none()
    if social is None:
        raise NotFoundError(
            detail=f"Social account config with ID {social_id} not found for branch {branch_id}"
        )
    return social


@router.put(
    "/{branch_id}/social-accounts/{social_id}",
    response_model=SocialAccountConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a social account config",
)
async def update_social_account_config(
    branch_id: int,
    social_id: int,
    data: SocialAccountConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SocialAccountConfig:
    """Update a social account config."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    social_result = await db.execute(
        select(SocialAccountConfig).where(
            SocialAccountConfig.id == social_id,
            SocialAccountConfig.branch_id == branch_id,
        )
    )
    social = social_result.scalar_one_or_none()
    if social is None:
        raise NotFoundError(
            detail=f"Social account config with ID {social_id} not found for branch {branch_id}"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(social, field, value)

    await db.commit()
    await db.refresh(social)
    return social


@router.delete(
    "/{branch_id}/social-accounts/{social_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a social account config",
)
async def delete_social_account_config(
    branch_id: int,
    social_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a social account config."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    social_result = await db.execute(
        select(SocialAccountConfig).where(
            SocialAccountConfig.id == social_id,
            SocialAccountConfig.branch_id == branch_id,
        )
    )
    social = social_result.scalar_one_or_none()
    if social is None:
        raise NotFoundError(
            detail=f"Social account config with ID {social_id} not found for branch {branch_id}"
        )

    await db.delete(social)
    await db.commit()


# ---------------------------------------------------------------------------
# ERP Connection Config endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{branch_id}/erp-connections",
    response_model=list[ERPConnectionConfigResponse],
    status_code=status.HTTP_200_OK,
    summary="List ERP connection configs for a branch",
)
async def list_erp_connection_configs(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ERPConnectionConfig]:
    """List all ERP connection configs for a branch (tenant isolated)."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    erp_result = await db.execute(
        select(ERPConnectionConfig).where(
            ERPConnectionConfig.branch_id == branch_id
        )
    )
    return erp_result.scalars().all()


@router.post(
    "/{branch_id}/erp-connections",
    response_model=ERPConnectionConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an ERP connection config for a branch",
)
async def create_erp_connection_config(
    branch_id: int,
    data: ERPConnectionConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ERPConnectionConfig:
    """Create a new ERP connection config for a branch."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    erp = ERPConnectionConfig(
        branch_id=branch_id,
        provider=data.provider,
        api_base_url=data.api_base_url,
        api_key=data.api_key,
        api_secret=data.api_secret,
        webhook_secret=data.webhook_secret,
        location_id=data.location_id,
        terminal_id=data.terminal_id,
        is_active=data.is_active,
        sync_enabled=data.sync_enabled,
        sync_interval_minutes=data.sync_interval_minutes,
        settings_json=data.settings_json,
    )
    db.add(erp)
    await db.commit()
    await db.refresh(erp)
    return erp


@router.get(
    "/{branch_id}/erp-connections/{erp_id}",
    response_model=ERPConnectionConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single ERP connection config",
)
async def get_erp_connection_config(
    branch_id: int,
    erp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ERPConnectionConfig:
    """Get a single ERP connection config by ID."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    erp_result = await db.execute(
        select(ERPConnectionConfig).where(
            ERPConnectionConfig.id == erp_id,
            ERPConnectionConfig.branch_id == branch_id,
        )
    )
    erp = erp_result.scalar_one_or_none()
    if erp is None:
        raise NotFoundError(
            detail=f"ERP connection config with ID {erp_id} not found for branch {branch_id}"
        )
    return erp


@router.put(
    "/{branch_id}/erp-connections/{erp_id}",
    response_model=ERPConnectionConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an ERP connection config",
)
async def update_erp_connection_config(
    branch_id: int,
    erp_id: int,
    data: ERPConnectionConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ERPConnectionConfig:
    """Update an ERP connection config."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    erp_result = await db.execute(
        select(ERPConnectionConfig).where(
            ERPConnectionConfig.id == erp_id,
            ERPConnectionConfig.branch_id == branch_id,
        )
    )
    erp = erp_result.scalar_one_or_none()
    if erp is None:
        raise NotFoundError(
            detail=f"ERP connection config with ID {erp_id} not found for branch {branch_id}"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(erp, field, value)

    await db.commit()
    await db.refresh(erp)
    return erp


@router.delete(
    "/{branch_id}/erp-connections/{erp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an ERP connection config",
)
async def delete_erp_connection_config(
    branch_id: int,
    erp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an ERP connection config."""
    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    await _require_branch_access(branch, current_user)

    erp_result = await db.execute(
        select(ERPConnectionConfig).where(
            ERPConnectionConfig.id == erp_id,
            ERPConnectionConfig.branch_id == branch_id,
        )
    )
    erp = erp_result.scalar_one_or_none()
    if erp is None:
        raise NotFoundError(
            detail=f"ERP connection config with ID {erp_id} not found for branch {branch_id}"
        )

    await db.delete(erp)
    await db.commit()
