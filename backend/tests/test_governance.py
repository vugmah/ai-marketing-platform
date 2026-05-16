"""Tests for Data Governance & GDPR/KVKK Compliance module.

Covers:
- Soft delete mixin
- GDPR data export (Article 20)
- GDPR data deletion (Article 17)
- Company/branch archiving
- Retention policy enforcement
"""

import pytest
from datetime import datetime, timedelta
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branches.models import Branch
from app.companies.models import Company
from app.governance.models import (
    GDPRDeletionRequest,
    GDPRRequestStatus,
    GDPRExportRequest,
    RetentionPolicyRun,
)
from app.governance.retention import RetentionPolicyEnforcer
from app.governance.service import ArchiveService, GDPRService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def test_company(db: AsyncSession) -> Company:
    """Create a test company."""
    company = Company(
        name="Governance Test Company",
        slug="governance-test",
        email="test@governance.com",
        plan="starter",
        is_active=True,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@pytest.fixture
async def test_branch(db: AsyncSession, test_company: Company) -> Branch:
    """Create a test branch."""
    branch = Branch(
        company_id=test_company.id,
        name="Governance Test Branch",
        slug="governance-branch",
        city="Istanbul",
        is_active=True,
    )
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


@pytest.fixture
async def test_user(db: AsyncSession, test_company: Company, test_branch: Branch) -> User:
    """Create a test user."""
    user = User(
        email="governance@test.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="Governance",
        role="company_admin",
        status="active",
        company_id=test_company.id,
        branch_id=test_branch.id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# =============================================================================
# Soft Delete Mixin Tests
# =============================================================================


class TestSoftDeleteMixin:
    """Tests for SoftDeleteMixin functionality."""

    @pytest.mark.asyncio
    async def test_soft_delete_mixin_columns_exist(self, db: AsyncSession, test_user: User):
        """Verify soft-delete columns exist on User model."""
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert hasattr(user, "deleted_at")
        assert hasattr(user, "deleted_by")
        assert hasattr(user, "is_deleted")
        assert user.is_deleted is False
        assert user.deleted_at is None
        assert user.deleted_by is None

    @pytest.mark.asyncio
    async def test_soft_delete_user(self, db: AsyncSession, test_user: User):
        """Test soft-deleting a user."""
        test_user.soft_delete(deleted_by=1)
        await db.commit()

        assert test_user.is_deleted is True
        assert test_user.deleted_at is not None
        assert test_user.deleted_by == 1

    @pytest.mark.asyncio
    async def test_restore_soft_deleted_user(self, db: AsyncSession, test_user: User):
        """Test restoring a soft-deleted user."""
        test_user.soft_delete(deleted_by=1)
        await db.commit()

        test_user.restore()
        await db.commit()

        assert test_user.is_deleted is False
        assert test_user.deleted_at is None
        assert test_user.deleted_by is None


# =============================================================================
# GDPR Export Tests
# =============================================================================


class TestGDPRExport:
    """Tests for GDPR data export (Article 20)."""

    @pytest.mark.asyncio
    async def test_export_user_data(self, db: AsyncSession, test_user: User, test_company: Company):
        """Test exporting user data."""
        export_data = await GDPRService.export_user_data(
            db=db,
            user_id=test_user.id,
            company_id=test_company.id,
            scopes=["user", "company"],
            requested_by=test_user.id,
        )

        assert "export_metadata" in export_data
        assert export_data["user"] is not None
        assert export_data["user"]["id"] == test_user.id
        assert export_data["user"]["email"] == test_user.email
        assert export_data["company"] is not None
        assert export_data["company"]["id"] == test_company.id

    @pytest.mark.asyncio
    async def test_export_request_recorded(self, db: AsyncSession, test_user: User, test_company: Company):
        """Test that export request is recorded in the database."""
        await GDPRService.export_user_data(
            db=db,
            user_id=test_user.id,
            company_id=test_company.id,
            scopes=["user"],
            requested_by=test_user.id,
        )

        result = await db.execute(
            select(GDPRExportRequest).where(
                GDPRExportRequest.user_id == test_user.id
            )
        )
        export_req = result.scalar_one_or_none()

        assert export_req is not None
        assert export_req.status == GDPRRequestStatus.COMPLETED
        assert export_req.record_count > 0


# =============================================================================
# GDPR Delete Tests
# =============================================================================


class TestGDPRDelete:
    """Tests for GDPR data deletion (Article 17)."""

    @pytest.mark.asyncio
    async def test_delete_user_data(self, db: AsyncSession, test_user: User, test_company: Company):
        """Test hard-deleting user data."""
        # Create deletion request record first
        affected = await GDPRService.delete_user_data(
            db=db,
            user_id=test_user.id,
            company_id=test_company.id,
            scopes=["user"],
            requested_by=test_user.id,
        )

        assert "users" in affected
        assert affected["users"] == 1

        # Verify user is deleted
        result = await db.execute(
            select(User).where(User.id == test_user.id)
        )
        assert result.scalar_one_or_none() is None


# =============================================================================
# Archive Tests
# =============================================================================


class TestArchiveService:
    """Tests for company and branch archiving."""

    @pytest.mark.asyncio
    async def test_archive_company(
        self, db: AsyncSession, test_company: Company, test_branch: Branch, test_user: User
    ):
        """Test archiving a company."""
        result = await ArchiveService.archive_company(
            db=db,
            company_id=test_company.id,
            archived_by=test_user.id,
        )

        assert result["is_archived"] is True
        assert result["archived_by"] == test_user.id
        assert result["affected_branches"] >= 1
        assert result["affected_users"] >= 1

        # Verify company is deactivated
        company_result = await db.execute(
            select(Company).where(Company.id == test_company.id)
        )
        company = company_result.scalar_one()
        assert company.is_active is False

    @pytest.mark.asyncio
    async def test_unarchive_company(self, db: AsyncSession, test_company: Company, test_user: User):
        """Test restoring an archived company."""
        # First archive
        await ArchiveService.archive_company(
            db=db, company_id=test_company.id, archived_by=test_user.id
        )

        # Then unarchive
        result = await ArchiveService.unarchive_company(
            db=db, company_id=test_company.id
        )

        assert result["is_archived"] is False
        assert result["is_deleted"] is False

        company_result = await db.execute(
            select(Company).where(Company.id == test_company.id)
        )
        company = company_result.scalar_one()
        assert company.is_active is True

    @pytest.mark.asyncio
    async def test_archive_branch(
        self, db: AsyncSession, test_branch: Branch, test_user: User
    ):
        """Test archiving a branch."""
        result = await ArchiveService.archive_branch(
            db=db,
            branch_id=test_branch.id,
            company_id=test_branch.company_id,
            archived_by=test_user.id,
        )

        assert result["is_archived"] is True
        assert result["archived_by"] == test_user.id

        # Verify branch is deactivated
        branch_result = await db.execute(
            select(Branch).where(Branch.id == test_branch.id)
        )
        branch = branch_result.scalar_one()
        assert branch.is_active is False


# =============================================================================
# Retention Policy Tests
# =============================================================================


class TestRetentionPolicy:
    """Tests for retention policy enforcement."""

    @pytest.mark.asyncio
    async def test_retention_enforcer_initialization(self):
        """Test retention policy enforcer initializes with defaults."""
        enforcer = RetentionPolicyEnforcer()

        assert len(enforcer.policies) == 6
        policy_names = [p["policy_name"] for p in enforcer.policies]
        assert "audit_logs_retention" in policy_names
        assert "ai_usage_logs_retention" in policy_names
        assert "gdpr_export_retention" in policy_names
        assert "dead_letter_events_retention" in policy_names

    @pytest.mark.asyncio
    async def test_retention_policy_days(self):
        """Test retention periods are correct."""
        enforcer = RetentionPolicyEnforcer()

        audit_policy = next(
            p for p in enforcer.policies if p["policy_name"] == "audit_logs_retention"
        )
        assert audit_policy["retention_days"] == 365  # 1 year

        ai_policy = next(
            p for p in enforcer.policies if p["policy_name"] == "ai_usage_logs_retention"
        )
        assert ai_policy["retention_days"] == 180  # 6 months

        export_policy = next(
            p for p in enforcer.policies if p["policy_name"] == "gdpr_export_retention"
        )
        assert export_policy["retention_days"] == 30  # 30 days

        dead_letter_policy = next(
            p for p in enforcer.policies if p["policy_name"] == "dead_letter_events_retention"
        )
        assert dead_letter_policy["retention_days"] == 90  # 90 days

    @pytest.mark.asyncio
    async def test_preview_policy(self, db: AsyncSession):
        """Test retention policy preview (dry run)."""
        enforcer = RetentionPolicyEnforcer()

        preview = await enforcer.preview_policy(db, "audit_logs_retention")

        assert "would_delete" in preview
        assert "total_records" in preview
        assert "remaining_after" in preview
        assert preview["policy_name"] == "audit_logs_retention"
        assert preview["retention_days"] == 365

    @pytest.mark.asyncio
    async def test_policy_status(self, db: AsyncSession):
        """Test getting retention policy status."""
        enforcer = RetentionPolicyEnforcer()

        status_list = await enforcer.get_policy_status(db)

        assert len(status_list) == 6
        for status in status_list:
            assert "policy_name" in status
            assert "retention_days" in status
            assert "current_record_count" in status


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestGovernanceAPI:
    """Integration tests for governance API endpoints."""

    @pytest.mark.asyncio
    async def test_list_retention_policies(self, client: AsyncClient, auth_headers: dict):
        """Test listing retention policies via API."""
        response = await client.get(
            "/api/v2/governance/retention/policies",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        policies = response.json()
        assert len(policies) >= 4
        policy_names = [p["policy_name"] for p in policies]
        assert "audit_logs_retention" in policy_names

    @pytest.mark.asyncio
    async def test_get_retention_status(self, client: AsyncClient, auth_headers: dict):
        """Test getting retention policy status via API."""
        response = await client.get(
            "/api/v2/governance/retention/status",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        status_list = response.json()
        assert len(status_list) >= 4

    @pytest.mark.asyncio
    async def test_preview_retention_policy(self, client: AsyncClient, auth_headers: dict):
        """Test previewing retention policy impact via API."""
        response = await client.get(
            "/api/v2/governance/retention/preview?policy_name=audit_logs_retention",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        preview = response.json()
        assert "would_delete" in preview
        assert preview["policy_name"] == "audit_logs_retention"
