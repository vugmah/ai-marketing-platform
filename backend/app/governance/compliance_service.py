"""Enterprise Compliance Layer service - Phase 4."""

from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.compliance_models import AuditRetentionPolicy, DataLineageRecord, PIIDataClassification, ComplianceReport, AdminActionLog


class ComplianceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_retention_policies(self, company_id: int) -> List[AuditRetentionPolicy]:
        result = await self.db.execute(
            select(AuditRetentionPolicy).where(AuditRetentionPolicy.company_id == company_id)
        )
        return result.scalars().all()

    async def set_retention_policy(
        self, company_id: int, data_category: str, retention_days: int,
        auto_archive: bool = True, auto_delete: bool = False
    ) -> AuditRetentionPolicy:
        result = await self.db.execute(
            select(AuditRetentionPolicy).where(
                AuditRetentionPolicy.company_id == company_id,
                AuditRetentionPolicy.data_category == data_category,
            )
        )
        policy = result.scalar_one_or_none()
        if not policy:
            policy = AuditRetentionPolicy(
                company_id=company_id, data_category=data_category,
                retention_days=retention_days, auto_archive=auto_archive,
                auto_delete_after_retention=auto_delete,
            )
            self.db.add(policy)
        else:
            policy.retention_days = retention_days
            policy.auto_archive = auto_archive
            policy.auto_delete_after_retention = auto_delete
        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def record_lineage(
        self, company_id: int, operation: str, source_table: Optional[str] = None,
        source_id: Optional[int] = None, target_table: Optional[str] = None,
        target_id: Optional[int] = None, performed_by: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> DataLineageRecord:
        record = DataLineageRecord(
            company_id=company_id, operation=operation,
            source_table=source_table, source_id=source_id,
            target_table=target_table, target_id=target_id,
            performed_by=performed_by, metadata=metadata or {},
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_lineage(self, table_name: str, record_id: int, limit: int = 50) -> List[DataLineageRecord]:
        result = await self.db.execute(
            select(DataLineageRecord).where(
                (DataLineageRecord.source_table == table_name) & (DataLineageRecord.source_id == record_id) |
                (DataLineageRecord.target_table == table_name) & (DataLineageRecord.target_id == record_id)
            ).order_by(desc(DataLineageRecord.created_at)).limit(limit)
        )
        return result.scalars().all()

    async def log_admin_action(
        self, company_id: int, admin_id: int, action_type: str,
        target_table: Optional[str] = None, target_id: Optional[int] = None,
        old_values: Optional[dict] = None, new_values: Optional[dict] = None,
        reason: Optional[str] = None, ip: Optional[str] = None
    ) -> AdminActionLog:
        log = AdminActionLog(
            company_id=company_id, admin_id=admin_id, action_type=action_type,
            target_table=target_table, target_id=target_id,
            old_values=old_values, new_values=new_values,
            reason=reason, ip_address=ip,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_admin_actions(self, company_id: int, admin_id: Optional[int] = None, limit: int = 50) -> List[AdminActionLog]:
        query = select(AdminActionLog).where(AdminActionLog.company_id == company_id).order_by(desc(AdminActionLog.created_at)).limit(limit)
        if admin_id:
            query = query.where(AdminActionLog.admin_id == admin_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def generate_compliance_report(self, company_id: int, report_type: str, date: str, admin_id: int) -> ComplianceReport:
        """Generate a compliance report snapshot."""
        # Count admin actions
        action_result = await self.db.execute(
            select(func.count()).where(AdminActionLog.company_id == company_id)
        )
        action_count = action_result.scalar() or 0

        # Count lineage records
        lineage_result = await self.db.execute(
            select(func.count()).where(DataLineageRecord.company_id == company_id)
        )
        lineage_count = lineage_result.scalar() or 0

        # Count PII records
        pii_result = await self.db.execute(
            select(func.count()).where(PIIDataClassification.company_id == company_id)
        )
        pii_count = pii_result.scalar() or 0

        summaries = {
            "admin_actions": action_count,
            "data_lineage_records": lineage_count,
            "pii_classifications": pii_count,
        }

        report = ComplianceReport(
            company_id=company_id, report_type=report_type, report_date=date,
            title=f"{report_type.upper()} Compliance Report - {date}",
            summary=f"Generated compliance report with {action_count} admin actions, {lineage_count} lineage records, {pii_count} PII classifications.",
            data_points=summaries, issues_found=0,
            generated_by=admin_id,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report
