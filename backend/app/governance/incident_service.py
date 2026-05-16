"""Incident Management & Recovery service - Phase 5."""

from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.incident_models import OperationalIncident, IncidentTimelineEvent, AutoRecoveryPlaybook


class IncidentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_incident(
        self, incident_type: str, severity: str, title: str, description: str,
        affected_services: list, company_id: Optional[int] = None,
    ) -> OperationalIncident:
        incident = OperationalIncident(
            company_id=company_id,
            incident_type=incident_type,
            severity=severity,
            title=title,
            description=description,
            affected_services=affected_services,
            status="open",
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)

        # Add detection event
        event = IncidentTimelineEvent(
            incident_id=incident.id,
            event_type="detection",
            description=f"Incident detected: {title}",
        )
        self.db.add(event)
        await self.db.commit()
        return incident

    async def get_incidents(
        self, status: Optional[str] = None, severity: Optional[str] = None,
        company_id: Optional[int] = None, limit: int = 50,
    ) -> List[OperationalIncident]:
        query = select(OperationalIncident).order_by(desc(OperationalIncident.detected_at)).limit(limit)
        if status:
            query = query.where(OperationalIncident.status == status)
        if severity:
            query = query.where(OperationalIncident.severity == severity)
        if company_id:
            query = query.where(OperationalIncident.company_id == company_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_incident_timeline(self, incident_id: int) -> List[IncidentTimelineEvent]:
        result = await self.db.execute(
            select(IncidentTimelineEvent)
            .where(IncidentTimelineEvent.incident_id == incident_id)
            .order_by(IncidentTimelineEvent.created_at)
        )
        return result.scalars().all()

    async def add_timeline_event(
        self, incident_id: int, event_type: str, description: str, performed_by: Optional[int] = None,
    ) -> IncidentTimelineEvent:
        event = IncidentTimelineEvent(
            incident_id=incident_id,
            event_type=event_type,
            description=description,
            performed_by=performed_by,
        )
        self.db.add(event)

        if event_type in ("mitigation", "resolution"):
            result = await self.db.execute(
                select(OperationalIncident).where(OperationalIncident.id == incident_id)
            )
            incident = result.scalar_one()
            if event_type == "resolution":
                incident.status = "resolved"
                incident.resolved_at = func.now()
            elif event_type == "mitigation":
                incident.status = "mitigating"

        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_recovery_dashboard(self, company_id: Optional[int] = None) -> dict:
        open_q = select(func.count()).where(OperationalIncident.status.in_(["open", "investigating", "mitigating"]))
        if company_id:
            open_q = open_q.where(OperationalIncident.company_id == company_id)
        open_result = await self.db.execute(open_q)
        open_count = open_result.scalar()

        resolved_q = select(func.count()).where(OperationalIncident.status == "resolved")
        if company_id:
            resolved_q = resolved_q.where(OperationalIncident.company_id == company_id)
        resolved_result = await self.db.execute(resolved_q)
        resolved_count = resolved_result.scalar()

        return {
            "open_incidents": open_count,
            "resolved_today": resolved_count,
            "critical": open_count,
            "status": "healthy" if open_count == 0 else "degraded" if open_count < 3 else "critical",
        }

    async def get_playbooks(self) -> List[AutoRecoveryPlaybook]:
        result = await self.db.execute(
            select(AutoRecoveryPlaybook).where(AutoRecoveryPlaybook.active == True)
        )
        return result.scalars().all()
