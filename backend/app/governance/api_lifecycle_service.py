"""API Lifecycle service layer."""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.api_lifecycle_models import (
    APIVersionPolicy,
    APIEndpointLifecycle,
    APIChangelogEntry,
    APIContractSnapshot,
)


class APIVersioningService:
    """Service for API versioning and lifecycle management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_version_policy(self, company_id: int) -> Optional[APIVersionPolicy]:
        result = await self.db.execute(
            select(APIVersionPolicy).where(APIVersionPolicy.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update_policy(
        self, company_id: int, current_version: str = "v2", min_version: str = "v2"
    ) -> APIVersionPolicy:
        policy = await self.get_version_policy(company_id)
        if not policy:
            policy = APIVersionPolicy(
                company_id=company_id,
                current_version=current_version,
                min_supported_version=min_version,
            )
            self.db.add(policy)
        else:
            policy.current_version = current_version
            policy.min_supported_version = min_version
            policy.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def deprecate_endpoint(
        self,
        company_id: int,
        method: str,
        path: str,
        removal_version: str,
        alternative: Optional[str] = None,
        migration_guide: Optional[str] = None,
    ) -> APIEndpointLifecycle:
        endpoint = APIEndpointLifecycle(
            company_id=company_id,
            method=method.upper(),
            path=path,
            lifecycle_status="deprecated",
            deprecated_at=datetime.utcnow(),
            sunset_at=datetime.utcnow() + timedelta(days=90),
            removal_version=removal_version,
            alternative_endpoint=alternative,
            migration_guide=migration_guide,
        )
        self.db.add(endpoint)
        await self.db.commit()
        await self.db.refresh(endpoint)
        return endpoint

    async def check_endpoint_status(
        self, method: str, path: str, company_id: Optional[int] = None
    ) -> Optional[APIEndpointLifecycle]:
        query = select(APIEndpointLifecycle).where(
            and_(
                APIEndpointLifecycle.method == method.upper(),
                APIEndpointLifecycle.path == path,
            )
        )
        if company_id:
            query = query.where(APIEndpointLifecycle.company_id == company_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_deprecated_endpoints(
        self, company_id: Optional[int] = None
    ) -> List[APIEndpointLifecycle]:
        query = select(APIEndpointLifecycle).where(
            APIEndpointLifecycle.lifecycle_status.in_(["deprecated", "sunset"])
        )
        if company_id:
            query = query.where(APIEndpointLifecycle.company_id == company_id)
        query = query.order_by(APIEndpointLifecycle.deprecated_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def add_changelog_entry(
        self,
        version: str,
        change_type: str,
        description: str,
        endpoint: Optional[str] = None,
        migration_required: bool = False,
        company_id: Optional[int] = None,
    ) -> APIChangelogEntry:
        entry = APIChangelogEntry(
            company_id=company_id,
            version=version,
            change_type=change_type,
            endpoint=endpoint,
            description=description,
            migration_required=migration_required,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_changelog(
        self,
        version: Optional[str] = None,
        change_type: Optional[str] = None,
        company_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[APIChangelogEntry]:
        query = select(APIChangelogEntry)
        if version:
            query = query.where(APIChangelogEntry.version == version)
        if change_type:
            query = query.where(APIChangelogEntry.change_type == change_type)
        if company_id:
            query = query.where(APIChangelogEntry.company_id == company_id)
        query = query.order_by(APIChangelogEntry.announced_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def snapshot_contract(
        self,
        endpoint_id: int,
        request_schema: dict,
        response_schema: dict,
        query_params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> APIContractSnapshot:
        import hashlib
        schema_str = str(sorted(request_schema.items())) + str(sorted(response_schema.items()))
        snapshot_hash = hashlib.sha256(schema_str.encode()).hexdigest()

        snapshot = APIContractSnapshot(
            endpoint_id=endpoint_id,
            snapshot_hash=snapshot_hash,
            request_schema=request_schema,
            response_schema=response_schema,
            query_params=query_params or {},
            headers=headers or {},
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def detect_contract_drift(
        self, endpoint_id: int, current_request: dict, current_response: dict
    ) -> Optional[dict]:
        result = await self.db.execute(
            select(APIContractSnapshot)
            .where(APIContractSnapshot.endpoint_id == endpoint_id)
            .order_by(APIContractSnapshot.snapshot_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if not last:
            return None

        import hashlib
        current_str = str(sorted(current_request.items())) + str(sorted(current_response.items()))
        current_hash = hashlib.sha256(current_str.encode()).hexdigest()

        if current_hash != last.snapshot_hash:
            return {
                "drift_detected": True,
                "last_snapshot": last.snapshot_at.isoformat(),
                "last_hash": last.snapshot_hash[:16],
                "current_hash": current_hash[:16],
                "endpoint_id": endpoint_id,
            }
        return {"drift_detected": False}
