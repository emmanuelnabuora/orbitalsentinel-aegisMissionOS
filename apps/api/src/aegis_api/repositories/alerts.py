from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.alert import Alert
from aegis_api.models.enums import AlertSeverity, AlertStatus


class AlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, alert_id: uuid.UUID) -> Alert | None:
        return await self.session.get(Alert, alert_id)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        workspace_id: uuid.UUID | None = None,
        allowed_markings: list[str] | None = None,
        severity: AlertSeverity | None = None,
        status: AlertStatus | None = None,
        asset_id: uuid.UUID | None = None,
        incident_id: uuid.UUID | None = None,
    ) -> tuple[list[Alert], int]:
        conditions = []
        if workspace_id is not None:
            conditions.append(Alert.workspace_id == workspace_id)
        if allowed_markings is not None:
            conditions.append(Alert.classification.in_(allowed_markings))
        if severity is not None:
            conditions.append(Alert.severity == severity)
        if status is not None:
            conditions.append(Alert.status == status)
        if asset_id is not None:
            conditions.append(Alert.asset_id == asset_id)
        if incident_id is not None:
            conditions.append(Alert.incident_id == incident_id)
        total = (
            await self.session.execute(sa.select(sa.func.count(Alert.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            sa.select(Alert)
            .where(*conditions)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars()), total

    async def count_open(self, *, severity: AlertSeverity | None = None) -> int:
        conditions = [Alert.status != AlertStatus.RESOLVED]
        if severity is not None:
            conditions.append(Alert.severity == severity)
        return (
            await self.session.execute(sa.select(sa.func.count(Alert.id)).where(*conditions))
        ).scalar_one()

    async def open_by_asset(self, asset_ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not asset_ids:
            return {}
        stmt = (
            sa.select(Alert.asset_id, sa.func.count(Alert.id))
            .where(Alert.asset_id.in_(asset_ids), Alert.status != AlertStatus.RESOLVED)
            .group_by(Alert.asset_id)
        )
        return dict((await self.session.execute(stmt)).all())

    def add(self, alert: Alert) -> None:
        self.session.add(alert)
