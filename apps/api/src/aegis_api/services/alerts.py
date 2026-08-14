import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import NotFoundError
from aegis_api.models.alert import Alert
from aegis_api.repositories.alerts import AlertRepository
from aegis_api.repositories.assets import AssetRepository
from aegis_api.schemas.alert import AlertCreate, AlertRead, AlertUpdate
from aegis_api.services.audit import AuditService


def to_read(alert: Alert) -> AlertRead:
    data = AlertRead.model_validate(alert)
    data.asset_name = alert.asset.name if alert.asset else None
    return data


class AlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AlertRepository(session)
        self.assets = AssetRepository(session)
        self.audit = AuditService(session)

    async def get(self, alert_id: uuid.UUID) -> Alert:
        alert = await self.repo.get(alert_id)
        if alert is None:
            raise NotFoundError("Alert not found")
        return alert

    async def create(
        self, data: AlertCreate, *, actor_id: uuid.UUID, workspace_id: uuid.UUID | None = None
    ) -> Alert:
        if data.asset_id is not None and await self.assets.get(data.asset_id) is None:
            raise NotFoundError("Asset not found")
        alert = Alert(**data.model_dump(), workspace_id=workspace_id)
        self.repo.add(alert)
        await self.session.flush()
        from aegis_api.models.enums import AlertSeverity as _Sev

        if workspace_id is not None and alert.severity == _Sev.CRITICAL:
            from aegis_api.services.notifications import NotificationService

            await NotificationService(self.session).notify_workspace_admins(
                workspace_id=workspace_id,
                kind="alert.critical",
                title=f"Critical alert: {alert.title}",
                link="/alerts",
            )
        self.audit.record(
            actor_id=actor_id,
            action="alert.created",
            resource_type="alert",
            resource_id=alert.id,
            detail={"severity": data.severity.value},
        )
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def update(self, alert_id: uuid.UUID, data: AlertUpdate, *, actor_id: uuid.UUID) -> Alert:
        alert = await self.get(alert_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(alert, field, value)
        self.audit.record(
            actor_id=actor_id,
            action="alert.updated",
            resource_type="alert",
            resource_id=alert.id,
            detail={"fields": sorted(changes)},
        )
        await self.session.commit()
        await self.session.refresh(alert)
        return alert
