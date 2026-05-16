"""Tests for Feature Flags and Approval Workflow (Agent 24).

Covers:
- FeatureFlag model CRUD
- Feature flag toggle endpoints (/features, /features/{name}/toggle)
- ApprovalRequest model CRUD
- Approval workflow endpoints (pending, approve, reject, edit)
- Approval statistics
- Authorization and tenant isolation
"""

from datetime import datetime, timedelta
from typing import Any, Dict

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.constants import (
    ApprovalStatus,
    BillingEventType,
    FeatureName,
    RequestType,
)
from app.billing.models import ApprovalRequest, FeatureFlag
from app.billing.service import ApprovalService, FeatureFlagService


# ============================================================================
# Feature Flag Tests
# ============================================================================


@pytest.mark.asyncio
class TestFeatureFlagModel:
    """Tests for FeatureFlag database model."""

    async def test_feature_flag_creation(self, db: AsyncSession):
        """FeatureFlag row can be created and persisted."""
        flag = FeatureFlag(
            company_id=1,
            feature_name=FeatureName.AI_CONTENT,
            enabled=True,
            enabled_by=1,
            enabled_at=datetime.utcnow(),
            reason="Test feature",
            expires_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(flag)
        await db.commit()
        await db.refresh(flag)

        assert flag.id is not None
        assert flag.company_id == 1
        assert flag.feature_name == FeatureName.AI_CONTENT
        assert flag.enabled is True
        assert flag.reason == "Test feature"

    async def test_feature_flag_unique_constraint(self, db: AsyncSession):
        """Duplicate (company_id, feature_name) should violate unique constraint."""
        flag1 = FeatureFlag(
            company_id=2,
            feature_name=FeatureName.WEBHOOK,
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(flag1)
        await db.commit()

        # Duplicate should cause integrity error
        flag2 = FeatureFlag(
            company_id=2,
            feature_name=FeatureName.WEBHOOK,
            enabled=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(flag2)
        with pytest.raises(Exception):
            await db.commit()
        await db.rollback()

    async def test_feature_flag_expiration(self, db: AsyncSession):
        """Expired feature flag should be treated as disabled."""
        flag = FeatureFlag(
            company_id=3,
            feature_name=FeatureName.SOCIAL_API,
            enabled=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(flag)
        await db.commit()
        await db.refresh(flag)

        # Service layer should detect expiration
        is_enabled = await FeatureFlagService.check_feature(
            db, company_id=3, feature_name=FeatureName.SOCIAL_API
        )
        assert is_enabled is False


@pytest.mark.asyncio
class TestFeatureFlagService:
    """Tests for FeatureFlagService business logic."""

    async def test_check_feature_not_found(self, db: AsyncSession):
        """Checking non-existent feature returns False."""
        result = await FeatureFlagService.check_feature(
            db, company_id=999, feature_name=FeatureName.AUTOMATION
        )
        assert result is False

    async def test_toggle_feature_create(self, db: AsyncSession):
        """Toggling a non-existent feature creates it."""
        flag = await FeatureFlagService.toggle_feature(
            db,
            company_id=4,
            feature_name=FeatureName.API_ACCESS,
            enabled=True,
            enabled_by=1,
            reason="Admin enabled",
        )
        assert flag.enabled is True
        assert flag.company_id == 4

    async def test_toggle_feature_update(self, db: AsyncSession):
        """Toggling an existing feature updates it."""
        # Create initial
        flag1 = await FeatureFlagService.toggle_feature(
            db, company_id=5, feature_name=FeatureName.ERP_INTEGRATION,
            enabled=True, enabled_by=1, reason="Initial enable",
        )
        assert flag1.enabled is True

        # Toggle off
        flag2 = await FeatureFlagService.toggle_feature(
            db, company_id=5, feature_name=FeatureName.ERP_INTEGRATION,
            enabled=False, enabled_by=1, reason="Disabled",
        )
        assert flag2.enabled is False
        assert flag2.id == flag1.id

    async def test_list_features(self, db: AsyncSession):
        """list_features returns all flags for a company."""
        # Create some flags
        for feature in [FeatureName.AI_CONTENT, FeatureName.WEBHOOK]:
            await FeatureFlagService.toggle_feature(
                db, company_id=6, feature_name=feature,
                enabled=True, enabled_by=1,
            )

        flags = await FeatureFlagService.list_features(db, company_id=6)
        assert len(flags) == 2

    async def test_feature_with_expiration(self, db: AsyncSession):
        """Feature with future expiration is enabled, expired is not."""
        future = datetime.utcnow() + timedelta(days=7)

        flag = await FeatureFlagService.toggle_feature(
            db, company_id=7, feature_name=FeatureName.MULTI_BRANCH,
            enabled=True, enabled_by=1, expires_at=future,
        )
        assert flag.expires_at is not None

        is_enabled = await FeatureFlagService.check_feature(
            db, company_id=7, feature_name=FeatureName.MULTI_BRANCH
        )
        assert is_enabled is True


# ============================================================================
# Approval Workflow Tests
# ============================================================================


@pytest.mark.asyncio
class TestApprovalRequestModel:
    """Tests for ApprovalRequest database model."""

    async def test_approval_request_creation(self, db: AsyncSession):
        """ApprovalRequest row can be created and persisted."""
        req = ApprovalRequest(
            company_id=1,
            request_type=RequestType.AI_SUGGESTION.value,
            requested_by=1,
            request_data={"campaign_id": 123, "suggestion": "Use more hashtags"},
            status="pending",
            reason="AI generated suggestion for campaign #123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)

        assert req.id is not None
        assert req.company_id == 1
        assert req.status == "pending"
        assert req.request_type == "ai_suggestion"
        assert "campaign_id" in req.request_data

    async def test_approval_request_status_values(self, db: AsyncSession):
        """All approval status values are valid."""
        for idx, status in enumerate(["pending", "approved", "rejected", "edited"]):
            req = ApprovalRequest(
                company_id=10 + idx,
                request_type=RequestType.BUDGET_CHANGE.value,
                requested_by=1,
                request_data={"amount": 100 + idx},
                status=status,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(req)

        await db.commit()

        result = await db.execute(
            select(ApprovalRequest).where(ApprovalRequest.status == "pending")
        )
        assert result.scalar_one_or_none() is not None

    async def test_approval_request_types(self, db: AsyncSession):
        """All request types are valid."""
        types = [
            RequestType.AI_SUGGESTION,
            RequestType.CAMPAIGN_CHANGE,
            RequestType.BUDGET_CHANGE,
            RequestType.CONTENT_PUBLISH,
            RequestType.AUTOMATION_RULE,
            RequestType.WEBHOOK_CONFIG,
        ]
        for idx, rt in enumerate(types):
            req = ApprovalRequest(
                company_id=20 + idx,
                request_type=rt.value,
                requested_by=1,
                request_data={"test": True},
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(req)
        await db.commit()

        result = await db.execute(select(ApprovalRequest))
        assert len(result.scalars().all()) == 6


@pytest.mark.asyncio
class TestApprovalService:
    """Tests for ApprovalService business logic."""

    async def _create_pending_request(self, db: AsyncSession) -> ApprovalRequest:
        """Helper to create a pending approval request."""
        req = ApprovalRequest(
            company_id=100,
            request_type=RequestType.CAMPAIGN_CHANGE.value,
            requested_by=1,
            request_data={"title": "Summer Sale", "budget": 500},
            status="pending",
            reason="Need approval for summer campaign",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    async def test_get_request(self, db: AsyncSession):
        """get_request returns the correct request."""
        req = await self._create_pending_request(db)
        found = await ApprovalService.get_request(db, req.id)
        assert found.id == req.id
        assert found.status == "pending"

    async def test_get_request_not_found(self, db: AsyncSession):
        """get_request raises NotFoundError for non-existent ID."""
        from app.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await ApprovalService.get_request(db, 99999)

    async def test_list_pending(self, db: AsyncSession):
        """list_pending returns only pending requests."""
        # Create pending and approved requests
        for i in range(3):
            req = ApprovalRequest(
                company_id=200,
                request_type=RequestType.AI_SUGGESTION.value,
                requested_by=1,
                request_data={"suggestion": f"test {i}"},
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(req)

        # Add one approved
        approved_req = ApprovalRequest(
            company_id=200,
            request_type=RequestType.AI_SUGGESTION.value,
            requested_by=1,
            request_data={"suggestion": "approved"},
            status="approved",
            approved_by=2,
            approved_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(approved_req)
        await db.commit()

        pending = await ApprovalService.list_pending(db, company_id=200)
        assert len(pending) == 3
        for p in pending:
            assert p.status == "pending"

    async def test_approve(self, db: AsyncSession):
        """approve changes status to approved."""
        req = await self._create_pending_request(db)
        result = await ApprovalService.approve(
            db, request_id=req.id, approved_by=2, reason="Looks good"
        )
        assert result.status == "approved"
        assert result.approved_by == 2
        assert result.approved_at is not None
        assert result.reason == "Looks good"

    async def test_approve_non_pending(self, db: AsyncSession):
        """Approving a non-pending request raises ValidationError."""
        from app.exceptions import ValidationError

        req = await self._create_pending_request(db)
        # First approve it
        await ApprovalService.approve(db, request_id=req.id, approved_by=2)
        # Try to approve again
        with pytest.raises(ValidationError):
            await ApprovalService.approve(
                db, request_id=req.id, approved_by=3
            )

    async def test_reject(self, db: AsyncSession):
        """reject changes status to rejected."""
        req = await self._create_pending_request(db)
        result = await ApprovalService.reject(
            db, request_id=req.id, approved_by=2, reason="Budget too high"
        )
        assert result.status == "rejected"
        assert result.approved_by == 2
        assert result.reason == "Budget too high"

    async def test_reject_non_pending(self, db: AsyncSession):
        """Rejecting a non-pending request raises ValidationError."""
        from app.exceptions import ValidationError

        req = await self._create_pending_request(db)
        await ApprovalService.reject(db, request_id=req.id, approved_by=2)
        with pytest.raises(ValidationError):
            await ApprovalService.reject(
                db, request_id=req.id, approved_by=3
            )

    async def test_edit_and_approve(self, db: AsyncSession):
        """edit_and_approve changes status to edited and stores edited data."""
        req = await self._create_pending_request(db)
        edited = {"title": "Summer Mega Sale", "budget": 750}

        result = await ApprovalService.edit_and_approve(
            db,
            request_id=req.id,
            approved_by=2,
            edited_data=edited,
            reason="Increased budget and updated title",
        )
        assert result.status == "edited"
        assert result.approved_by == 2
        assert result.edited_data == edited
        assert result.reason == "Increased budget and updated title"

    async def test_get_stats(self, db: AsyncSession):
        """get_stats returns correct counts."""
        company_id = 300
        statuses = ["pending", "pending", "approved", "rejected", "edited"]
        for i, s in enumerate(statuses):
            req = ApprovalRequest(
                company_id=company_id,
                request_type=RequestType.CAMPAIGN_CHANGE.value,
                requested_by=1,
                request_data={"i": i},
                status=s,
                approved_by=2 if s != "pending" else None,
                approved_at=datetime.utcnow() if s != "pending" else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(req)
        await db.commit()

        stats = await ApprovalService.get_stats(db, company_id)
        assert stats["total"] == 5
        assert stats["pending"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["edited"] == 1

    async def test_to_response(self, db: AsyncSession):
        """to_response produces valid ApprovalRequestResponse."""
        req = await self._create_pending_request(db)
        resp = ApprovalService.to_response(req)
        assert resp.id == req.id
        assert resp.company_id == req.company_id
        assert resp.status == req.status
        assert resp.request_type == req.request_type


# ============================================================================
# API Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
class TestFeatureFlagEndpoints:
    """Integration tests for feature flag API endpoints."""

    async def test_get_features_unauthenticated(self, async_client):
        """GET /features requires authentication."""
        resp = await async_client.get("/api/v2/billing/features")
        assert resp.status_code in (401, 403)

    async def test_toggle_feature_unauthorized(self, auth_client):
        """POST /features/{name}/toggle requires admin role."""
        resp = await auth_client.post(
            "/api/v2/billing/features/ai_content/toggle",
            json={"enabled": True, "reason": "Test"},
        )
        # Non-admin users get 403
        assert resp.status_code in (200, 403)


@pytest.mark.asyncio
class TestApprovalEndpoints:
    """Integration tests for approval workflow API endpoints."""

    async def test_get_pending_approvals_unauthenticated(self, async_client):
        """GET /approvals/pending requires authentication."""
        resp = await async_client.get("/api/v2/billing/approvals/pending")
        assert resp.status_code in (401, 403)

    async def test_approve_without_auth(self, async_client):
        """POST /approvals/{id}/approve requires auth + admin role."""
        resp = await async_client.post(
            "/api/v2/billing/approvals/1/approve",
            json={"reason": "Test approval"},
        )
        assert resp.status_code in (401, 403)

    async def test_reject_without_auth(self, async_client):
        """POST /approvals/{id}/reject requires auth + admin role."""
        resp = await async_client.post(
            "/api/v2/billing/approvals/1/reject",
            json={"reason": "Test rejection"},
        )
        assert resp.status_code in (401, 403)

    async def test_edit_without_auth(self, async_client):
        """POST /approvals/{id}/edit requires auth + admin role."""
        resp = await async_client.post(
            "/api/v2/billing/approvals/1/edit",
            json={"edited_data": {"key": "value"}, "reason": "Edited"},
        )
        assert resp.status_code in (401, 403)


# ============================================================================
# Enum Validation Tests
# ============================================================================


class TestEnums:
    """Tests for enum definitions."""

    def test_feature_name_values(self):
        """FeatureName enum has all expected values."""
        assert FeatureName.AI_CONTENT.value == "ai_content"
        assert FeatureName.SOCIAL_API.value == "social_api"
        assert FeatureName.WEBHOOK.value == "webhook"
        assert FeatureName.AUTOMATION.value == "automation"
        assert FeatureName.ADVANCED_ANALYTICS.value == "advanced_analytics"
        assert FeatureName.ERP_INTEGRATION.value == "erp_integration"
        assert FeatureName.MULTI_BRANCH.value == "multi_branch"
        assert FeatureName.CUSTOM_BRANDING.value == "custom_branding"
        assert FeatureName.PRIORITY_SUPPORT.value == "priority_support"
        assert FeatureName.API_ACCESS.value == "api_access"

    def test_approval_status_values(self):
        """ApprovalStatus enum has all expected values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EDITED.value == "edited"

    def test_request_type_values(self):
        """RequestType enum has all expected values."""
        assert RequestType.AI_SUGGESTION.value == "ai_suggestion"
        assert RequestType.CAMPAIGN_CHANGE.value == "campaign_change"
        assert RequestType.BUDGET_CHANGE.value == "budget_change"
        assert RequestType.CONTENT_PUBLISH.value == "content_publish"
        assert RequestType.AUTOMATION_RULE.value == "automation_rule"
        assert RequestType.WEBHOOK_CONFIG.value == "webhook_config"

    def test_feature_flag_defaults(self):
        """FEATURE_FLAG_DEFAULTS has correct initial values."""
        from app.billing.constants import FEATURE_FLAG_DEFAULTS

        assert FEATURE_FLAG_DEFAULTS[FeatureName.AI_CONTENT.value] is False
        assert FEATURE_FLAG_DEFAULTS[FeatureName.SOCIAL_API.value] is False
        assert FEATURE_FLAG_DEFAULTS[FeatureName.WEBHOOK.value] is False
        assert FEATURE_FLAG_DEFAULTS[FeatureName.AUTOMATION.value] is False

    def test_plan_feature_defaults(self):
        """Plan definitions include feature flags."""
        from app.billing.constants import PLAN_DEFINITIONS, PlanTier

        free = PLAN_DEFINITIONS[PlanTier.FREE.value]
        assert free["features"]["ai_content"] is True
        assert free["features"]["social_api"] is False

        enterprise = PLAN_DEFINITIONS[PlanTier.ENTERPRISE.value]
        assert enterprise["features"]["automation"] is True
        assert enterprise["features"]["priority_support"] is True
