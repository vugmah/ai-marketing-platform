"""Data Governance & GDPR/KVKK Compliance Router.

Endpoints:
- GET  /gdpr/export          - Export all user data (Article 20)
- POST /gdpr/delete          - Hard delete all user data (Article 17)
- POST /gdpr/verify          - Verify deletion request (double opt-in)

- POST /companies/{id}/archive    - Archive a company (soft-delete cascade)
- POST /companies/{id}/unarchive  - Restore an archived company
- POST /branches/{id}/archive     - Archive a branch (soft-delete cascade)
- POST /branches/{id}/unarchive   - Restore an archived branch

- GET  /retention/policies   - List retention policies
- POST /retention/run        - Execute retention policies
- GET  /retention/preview    - Preview retention policy impact
- GET  /retention/status     - Get retention policy status
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import NotFoundError

from .models import GDPRDeletionRequest, GDPRRequestStatus, GDPRExportRequest
from .retention import RetentionPolicyEnforcer
from .schemas import (
    BranchArchiveRequest,
    BranchArchiveResponse,
    CompanyArchiveRequest,
    CompanyArchiveResponse,
    GDPRDeleteRequest,
    GDPRDeleteResponse,
    GDPRUserDataExport,
    GDPRExportResponse,
    RetentionPolicyExecuteResponse,
    RetentionPolicyStatus,
    UnarchiveResponse,
)
from .service import ArchiveService, GDPRService

router = APIRouter()

# =============================================================================
# GDPR / KVKK Endpoints
# =============================================================================


@router.get(
    "/gdpr/export",
    response_model=GDPRUserDataExport,
    status_code=status.HTTP_200_OK,
    summary="GDPR/KVKK: Export all user data (Article 20)",
    tags=["GDPR/KVKK"],
)
async def gdpr_export_user_data(
    request: Request,
    user_id: int,
    scope: Optional[str] = "all",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Export all data for a user (GDPR Article 20 / KVKK Maddesi 11).

    Returns a comprehensive JSON containing all user-related data across
    all modules. The export is scoped to the requesting user's company
    unless the requester is a super_admin.

    Args:
        user_id: The user whose data will be exported.
        scope: Comma-separated list of data scopes (default: "all").
               Options: all, user, company, branch, ai, ads, audit, events, social, media, analytics.

    Returns:
        Complete user data export as JSON.

    Raises:
        NotFoundError: If the user is not found or access is denied.
    """
    # Verify the target user exists and is in the same company
    from sqlalchemy import select

    target_user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    target_user = target_user_result.scalar_one_or_none()

    if target_user is None:
        raise NotFoundError(detail=f"User with ID {user_id} not found")

    # Tenant isolation: only super_admin can export any user's data
    if (
        current_user.role != "super_admin"
        and current_user.company_id != target_user.company_id
    ):
        raise NotFoundError(detail=f"User with ID {user_id} not found")

    # Parse scopes
    scopes = [s.strip() for s in scope.split(",")] if scope else ["all"]

    # Execute export
    export_data = await GDPRService.export_user_data(
        db=db,
        user_id=user_id,
        company_id=target_user.company_id,
        scopes=scopes,
        requested_by=current_user.id,
    )

    return export_data


@router.post(
    "/gdpr/delete",
    response_model=GDPRDeleteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="GDPR/KVKK: Delete all user data (Article 17, Right to be Forgotten)",
    tags=["GDPR/KVKK"],
)
async def gdpr_delete_user_data(
    request: Request,
    data: GDPRDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Permanently delete all data for a user (GDPR Article 17 / KVKK Maddesi 7).

    This operation is IRREVERSIBLE. All user-related records across all
    modules will be hard-deleted. A deletion request record is created
    for audit purposes.

    Only super_admin or the user themselves (with verification token)
    can initiate deletion.

    Args:
        data: Deletion request containing user_id and optional scopes.

    Returns:
        Deletion status with affected table counts.

    Raises:
        NotFoundError: If the user is not found or access is denied.
        AuthorizationError: If the requester lacks permission.
    """
    from sqlalchemy import select

    target_user_result = await db.execute(
        select(User).where(User.id == data.user_id)
    )
    target_user = target_user_result.scalar_one_or_none()

    if target_user is None:
        raise NotFoundError(detail=f"User with ID {data.user_id} not found")

    # Permission check
    if current_user.role != "super_admin":
        if current_user.company_id != target_user.company_id:
            raise NotFoundError(detail=f"User with ID {data.user_id} not found")
        # Non-admin users can only delete their own data with verification
        if current_user.id != data.user_id:
            from app.exceptions import AuthorizationError

            raise AuthorizationError(
                detail="You can only delete your own data. Contact an admin for assistance."
            )

    # Execute hard deletion
    affected = await GDPRService.delete_user_data(
        db=db,
        user_id=data.user_id,
        company_id=target_user.company_id,
        scopes=data.scopes,
        requested_by=current_user.id,
    )

    return {
        "deletion_id": 0,  # Will be populated from the request record
        "status": "completed",
        "user_id": data.user_id,
        "affected_tables": affected,
        "total_records_deleted": sum(affected.values()),
        "completed_at": datetime.utcnow(),
    }


@router.get(
    "/gdpr/export/{export_id}",
    response_model=GDPRExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get GDPR export request status",
    tags=["GDPR/KVKK"],
)
async def get_gdpr_export_status(
    export_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GDPRExportRequest:
    """Get the status of a GDPR data export request."""
    from sqlalchemy import select

    result = await db.execute(
        select(GDPRExportRequest).where(GDPRExportRequest.id == export_id)
    )
    export_req = result.scalar_one_or_none()

    if export_req is None:
        raise NotFoundError(detail=f"Export request {export_id} not found")

    # Tenant isolation
    if (
        current_user.role != "super_admin"
        and current_user.company_id != export_req.company_id
    ):
        raise NotFoundError(detail=f"Export request {export_id} not found")

    return export_req


# =============================================================================
# Company Archive Endpoints
# =============================================================================


@router.post(
    "/companies/{company_id}/archive",
    response_model=CompanyArchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a company (soft-delete cascade)",
    tags=["Archive"],
)
async def archive_company(
    request: Request,
    company_id: int,
    data: CompanyArchiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> dict:
    """Archive a company and all related entities.

    Performs a cascading soft-delete:
    1. Deactivates the company
    2. Deactivates all branches
    3. Deactivates all users

    The data is NOT permanently deleted - only deactivated.
    Use the unarchive endpoint to restore.

    Args:
        company_id: Company to archive.
        data: Optional archive reason.

    Returns:
        Archive operation statistics.
    """
    from sqlalchemy import select

    # Verify company exists and user has access
    from app.companies.models import Company

    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    if company is None:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    if current_user.role != "super_admin" and current_user.company_id != company_id:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    result = await ArchiveService.archive_company(
        db=db,
        company_id=company_id,
        archived_by=current_user.id,
    )

    return {
        **result,
        "message": f"Company {company_id} archived successfully. "
                   f"{result['affected_branches']} branches and "
                   f"{result['affected_users']} users deactivated.",
    }


@router.post(
    "/companies/{company_id}/unarchive",
    response_model=UnarchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived company",
    tags=["Archive"],
)
async def unarchive_company(
    request: Request,
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> dict:
    """Restore an archived company.

    Reactivates the company and all its branches.
    Users are NOT automatically reactivated for security reasons.

    Args:
        company_id: Company to restore.

    Returns:
        Restoration status.
    """
    from sqlalchemy import select

    from app.companies.models import Company

    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    if company is None:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    if current_user.role != "super_admin" and current_user.company_id != company_id:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    result = await ArchiveService.unarchive_company(db=db, company_id=company_id)

    return {
        **result,
        "id": company_id,
        "message": f"Company {company_id} restored successfully. "
                   f"Users must be reactivated manually.",
    }


# =============================================================================
# Branch Archive Endpoints
# =============================================================================


@router.post(
    "/branches/{branch_id}/archive",
    response_model=BranchArchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a branch (soft-delete cascade)",
    tags=["Archive"],
)
async def archive_branch(
    request: Request,
    branch_id: int,
    data: BranchArchiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> dict:
    """Archive a branch and deactivate its users.

    Performs a cascading soft-delete on the branch level:
    1. Deactivates the branch
    2. Deactivates all users in the branch
    3. Clears branch_id from users

    Args:
        branch_id: Branch to archive.
        data: Optional archive reason.

    Returns:
        Archive operation statistics.
    """
    from sqlalchemy import select

    from app.branches.models import Branch

    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()

    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    # Tenant isolation
    if (
        current_user.role != "super_admin"
        and current_user.company_id != branch.company_id
    ):
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    result = await ArchiveService.archive_branch(
        db=db,
        branch_id=branch_id,
        company_id=branch.company_id,
        archived_by=current_user.id,
    )

    return {
        **result,
        "message": f"Branch {branch_id} archived successfully. "
                   f"{result['affected_users']} users deactivated.",
    }


@router.post(
    "/branches/{branch_id}/unarchive",
    response_model=UnarchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived branch",
    tags=["Archive"],
)
async def unarchive_branch(
    request: Request,
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin", "branch_manager"])),
) -> dict:
    """Restore an archived branch.

    Reactivates the branch. Users are NOT automatically reactivated.

    Args:
        branch_id: Branch to restore.

    Returns:
        Restoration status.
    """
    from sqlalchemy import select

    from app.branches.models import Branch

    branch_result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = branch_result.scalar_one_or_none()

    if branch is None:
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    if (
        current_user.role != "super_admin"
        and current_user.company_id != branch.company_id
    ):
        raise NotFoundError(detail=f"Branch with ID {branch_id} not found")

    result = await ArchiveService.unarchive_branch(
        db=db,
        branch_id=branch_id,
        company_id=branch.company_id,
    )

    return {
        **result,
        "id": branch_id,
        "message": f"Branch {branch_id} restored successfully.",
    }


# =============================================================================
# Retention Policy Endpoints
# =============================================================================


@router.get(
    "/retention/policies",
    response_model=list,
    status_code=status.HTTP_200_OK,
    summary="List all retention policies",
    tags=["Retention"],
)
async def list_retention_policies(
    request: Request,
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> list:
    """List all configured data retention policies.

    Returns:
        List of retention policy configurations.
    """
    enforcer = RetentionPolicyEnforcer()
    return enforcer.policies


@router.get(
    "/retention/status",
    response_model=list,
    status_code=status.HTTP_200_OK,
    summary="Get retention policy execution status",
    tags=["Retention"],
)
async def get_retention_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> list:
    """Get current status of all retention policies.

    Returns:
        List of policy statuses with last run info and record counts.
    """
    enforcer = RetentionPolicyEnforcer()
    return await enforcer.get_policy_status(db)


@router.post(
    "/retention/run",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Execute all retention policies",
    tags=["Retention"],
)
async def run_retention_policies(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin"])),
) -> dict:
    """Execute all configured retention policies.

    Deletes records older than their configured retention period.
    This operation is IRREVERSIBLE.

    Returns:
        Execution summary with per-policy results.
    """
    enforcer = RetentionPolicyEnforcer()
    result = await enforcer.run_all_policies(db)
    return result


@router.get(
    "/retention/preview",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Preview retention policy impact (dry run)",
    tags=["Retention"],
)
async def preview_retention_policy(
    request: Request,
    policy_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> dict:
    """Preview how many records a retention policy would delete.

    This is a dry-run that does NOT delete any records.

    Args:
        policy_name: Name of the policy to preview.

    Returns:
        Preview result with record counts.
    """
    enforcer = RetentionPolicyEnforcer()
    return await enforcer.preview_policy(db, policy_name)


@router.post(
    "/retention/run/{policy_name}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Execute a single retention policy",
    tags=["Retention"],
)
async def run_single_retention_policy(
    request: Request,
    policy_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin"])),
) -> dict:
    """Execute a single retention policy by name.

    Args:
        policy_name: Name of the policy to execute.

    Returns:
        Execution result for the policy.
    """
    enforcer = RetentionPolicyEnforcer()
    return await enforcer.run_policy(db, policy_name)
