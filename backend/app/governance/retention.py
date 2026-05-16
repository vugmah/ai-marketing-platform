"""Retention policy enforcement for GDPR/KVKK compliance.

Implements automatic data retention policies:
- Audit logs: 1 year
- AI usage logs: 6 months
- Export reports: 30 days
- Dead letter events: 90 days

Policies are executed via the RetentionPolicyEnforcer which can be
called from a scheduled Celery task or manually via API.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AIUsageLog
from app.audit.models import AuditLog, LoginAttempt
from app.events.models import DeadLetterEvent
from app.governance.models import RetentionPolicyRun

logger = logging.getLogger(__name__)

# =============================================================================
# Retention Policy Definitions
# =============================================================================

# Default retention policies (days -> retention period)
DEFAULT_POLICIES = [
    {
        "policy_name": "audit_logs_retention",
        "table_name": "audit_logs",
        "retention_days": 365,  # 1 year
        "date_column": "created_at",
        "description": "Audit logs retained for 1 year per GDPR/KVKK requirements",
    },
    {
        "policy_name": "ai_usage_logs_retention",
        "table_name": "ai_usage_logs",
        "retention_days": 180,  # 6 months
        "date_column": "created_at",
        "description": "AI usage logs retained for 6 months",
    },
    {
        "policy_name": "gdpr_export_retention",
        "table_name": "gdpr_export_requests",
        "retention_days": 30,  # 30 days
        "date_column": "created_at",
        "description": "GDPR export files and requests retained for 30 days",
    },
    {
        "policy_name": "dead_letter_events_retention",
        "table_name": "dead_letter_events",
        "retention_days": 90,  # 90 days
        "date_column": "created_at",
        "description": "Dead letter events retained for 90 days",
    },
    {
        "policy_name": "login_attempts_retention",
        "table_name": "login_attempts",
        "retention_days": 90,  # 90 days
        "date_column": "created_at",
        "description": "Login attempts retained for 90 days",
    },
    {
        "policy_name": "gdpr_deletion_retention",
        "table_name": "gdpr_deletion_requests",
        "retention_days": 365,  # 1 year
        "date_column": "created_at",
        "description": "GDPR deletion request records retained for 1 year (audit)",
    },
]

# SQLAlchemy model mapping for deletion
TABLE_MODEL_MAP = {
    "audit_logs": AuditLog,
    "ai_usage_logs": AIUsageLog,
    "dead_letter_events": DeadLetterEvent,
    "login_attempts": LoginAttempt,
}


# =============================================================================
# Retention Policy Enforcer
# =============================================================================


class RetentionPolicyEnforcer:
    """Enforces data retention policies across the platform.

    Executes retention policies by deleting records older than the
    configured retention period. Each execution is logged for audit.

    Usage:
        enforcer = RetentionPolicyEnforcer()
        result = await enforcer.run_all_policies(db)
        # or
        result = await enforcer.run_policy(db, "audit_logs_retention")
    """

    def __init__(self, policies: Optional[List[Dict[str, Any]]] = None):
        """Initialize with optional custom policy configuration.

        Args:
            policies: List of policy dictionaries. Uses DEFAULT_POLICIES if None.
        """
        self.policies = policies or DEFAULT_POLICIES

    async def run_all_policies(self, db: AsyncSession) -> Dict[str, Any]:
        """Execute all configured retention policies.

        Args:
            db: Async database session.

        Returns:
            Summary of execution results per policy.
        """
        results = []
        total_deleted = 0
        errors = []

        for policy in self.policies:
            try:
                policy_result = await self._execute_policy(db, policy)
                results.append(policy_result)
                total_deleted += policy_result.get("records_deleted", 0)
            except Exception as exc:
                error_msg = f"Policy '{policy['policy_name']}' failed: {str(exc)}"
                logger.error(error_msg)
                errors.append(error_msg)
                results.append(
                    {
                        "policy_name": policy["policy_name"],
                        "status": "failed",
                        "error": str(exc),
                        "records_deleted": 0,
                    }
                )

        return {
            "executed_at": datetime.utcnow().isoformat(),
            "policies_run": len(self.policies),
            "policies": results,
            "total_records_deleted": total_deleted,
            "errors": errors,
        }

    async def run_policy(self, db: AsyncSession, policy_name: str) -> Dict[str, Any]:
        """Execute a single retention policy by name.

        Args:
            db: Async database session.
            policy_name: Name of the policy to execute.

        Returns:
            Execution result for the policy.

        Raises:
            ValueError: If the policy name is not found.
        """
        policy = next(
            (p for p in self.policies if p["policy_name"] == policy_name), None
        )
        if not policy:
            raise ValueError(
                f"Policy '{policy_name}' not found. "
                f"Available: {[p['policy_name'] for p in self.policies]}"
            )

        return await self._execute_policy(db, policy)

    async def get_policy_status(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Get status of all retention policies (last run, record counts).

        Args:
            db: Async database session.

        Returns:
            List of policy status dictionaries.
        """
        status_list = []

        for policy in self.policies:
            # Get last run
            last_run_result = await db.execute(
                select(RetentionPolicyRun)
                .where(RetentionPolicyRun.policy_name == policy["policy_name"])
                .order_by(RetentionPolicyRun.created_at.desc())
                .limit(1)
            )
            last_run = last_run_result.scalar_one_or_none()

            # Get current record count
            model = TABLE_MODEL_MAP.get(policy["table_name"])
            current_count = 0
            if model:
                count_result = await db.execute(select(func.count(model.id)))
                current_count = count_result.scalar_one()

            status_list.append(
                {
                    "policy_name": policy["policy_name"],
                    "table_name": policy["table_name"],
                    "retention_days": policy["retention_days"],
                    "description": policy["description"],
                    "current_record_count": current_count,
                    "last_run": (
                        last_run.created_at.isoformat() if last_run else None
                    ),
                    "last_run_status": last_run.status if last_run else None,
                    "last_run_records_affected": (
                        last_run.records_affected if last_run else 0
                    ),
                }
            )

        return status_list

    async def _execute_policy(
        self,
        db: AsyncSession,
        policy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single retention policy.

        Args:
            db: Async database session.
            policy: Policy configuration dictionary.

        Returns:
            Execution result with records deleted and timing.
        """
        import time

        start_time = time.time()
        policy_name = policy["policy_name"]
        table_name = policy["table_name"]
        retention_days = policy["retention_days"]
        date_column = policy.get("date_column", "created_at")

        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Get the SQLAlchemy model
        model = TABLE_MODEL_MAP.get(table_name)
        if not model:
            raise ValueError(f"No model mapping found for table: {table_name}")

        # Build and execute delete query
        date_attr = getattr(model, date_column)
        delete_query = delete(model).where(date_attr < cutoff_date)

        result = await db.execute(delete_query)
        records_deleted = result.rowcount

        await db.commit()

        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        # Log the policy run
        run_log = RetentionPolicyRun(
            policy_name=policy_name,
            table_name=table_name,
            retention_days=retention_days,
            records_affected=records_deleted,
            execution_time_ms=execution_time_ms,
            status="success",
            cutoff_date=cutoff_date,
        )
        db.add(run_log)
        await db.commit()

        logger.info(
            "Retention policy '%s' executed: deleted %d records from %s "
            "older than %s (took %sms)",
            policy_name,
            records_deleted,
            table_name,
            cutoff_date.isoformat(),
            execution_time_ms,
        )

        return {
            "policy_name": policy_name,
            "table_name": table_name,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "records_deleted": records_deleted,
            "execution_time_ms": execution_time_ms,
            "status": "success",
        }

    async def preview_policy(
        self,
        db: AsyncSession,
        policy_name: str,
    ) -> Dict[str, Any]:
        """Preview how many records a policy would delete (dry run).

        Args:
            db: Async database session.
            policy_name: Name of the policy to preview.

        Returns:
            Preview result without actually deleting records.
        """
        policy = next(
            (p for p in self.policies if p["policy_name"] == policy_name), None
        )
        if not policy:
            raise ValueError(f"Policy '{policy_name}' not found")

        table_name = policy["table_name"]
        retention_days = policy["retention_days"]
        date_column = policy.get("date_column", "created_at")

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        model = TABLE_MODEL_MAP.get(table_name)
        if not model:
            raise ValueError(f"No model mapping found for table: {table_name}")

        # Count records that would be deleted
        date_attr = getattr(model, date_column)
        count_result = await db.execute(
            select(func.count(model.id)).where(date_attr < cutoff_date)
        )
        would_delete = count_result.scalar_one()

        # Total count
        total_result = await db.execute(select(func.count(model.id)))
        total_records = total_result.scalar_one()

        return {
            "policy_name": policy_name,
            "table_name": table_name,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "would_delete": would_delete,
            "total_records": total_records,
            "remaining_after": total_records - would_delete,
        }
