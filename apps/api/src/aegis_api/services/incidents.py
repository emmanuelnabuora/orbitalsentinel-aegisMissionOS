import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import NotFoundError
from aegis_api.models.incident import Incident, IncidentEvent
from aegis_api.repositories.alerts import AlertRepository
from aegis_api.repositories.incidents import IncidentRepository
from aegis_api.schemas.incident import IncidentCreate, IncidentUpdate
from aegis_api.services.audit import AuditService


class IncidentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IncidentRepository(session)
        self.alerts = AlertRepository(session)
        self.audit = AuditService(session)

    async def get(self, incident_id: uuid.UUID) -> Incident:
        incident = await self.repo.get(incident_id)
        if incident is None:
            raise NotFoundError("Incident not found")
        return incident

    async def create(
        self, data: IncidentCreate, *, actor_id: uuid.UUID, workspace_id: uuid.UUID | None = None
    ) -> Incident:
        incident = Incident(
            title=data.title,
            summary=data.summary,
            severity=data.severity,
            commander_id=actor_id,
            workspace_id=workspace_id,
        )
        self.repo.add(incident)
        await self.session.flush()
        self._event(incident.id, "created", f"Incident opened: {data.title}", actor_id)

        for alert_id in data.alert_ids:
            alert = await self.alerts.get(alert_id)
            if alert is None:
                raise NotFoundError(f"Alert {alert_id} not found")
            alert.incident_id = incident.id
            self._event(incident.id, "alert_linked", f"Alert linked: {alert.title}", actor_id)

        self.audit.record(
            actor_id=actor_id,
            action="incident.created",
            resource_type="incident",
            resource_id=incident.id,
        )
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def update(
        self, incident_id: uuid.UUID, data: IncidentUpdate, *, actor_id: uuid.UUID
    ) -> Incident:
        incident = await self.get(incident_id)
        changes = data.model_dump(exclude_unset=True)
        if "status" in changes and changes["status"] != incident.status:
            self._event(
                incident.id,
                "status",
                f"Status: {incident.status.value} -> {changes['status'].value}",
                actor_id,
            )
        for field, value in changes.items():
            setattr(incident, field, value)
        self.audit.record(
            actor_id=actor_id,
            action="incident.updated",
            resource_type="incident",
            resource_id=incident.id,
            detail={"fields": sorted(changes)},
        )
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def add_note(self, incident_id: uuid.UUID, message: str, *, actor_id: uuid.UUID) -> None:
        await self.get(incident_id)
        self._event(incident_id, "note", message, actor_id)
        self.audit.record(
            actor_id=actor_id,
            action="incident.note_added",
            resource_type="incident",
            resource_id=incident_id,
        )
        await self.session.commit()

    def _event(
        self, incident_id: uuid.UUID, kind: str, message: str, actor_id: uuid.UUID | None
    ) -> None:
        self.session.add(
            IncidentEvent(incident_id=incident_id, kind=kind, message=message, actor_id=actor_id)
        )
