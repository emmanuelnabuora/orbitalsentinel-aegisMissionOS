from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.enums import IncidentStatus
from aegis_api.models.incident import Incident


class IncidentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, incident_id: uuid.UUID) -> Incident | None:
        return await self.session.get(Incident, incident_id)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: IncidentStatus | None = None,
        workspace_id: uuid.UUID | None = None,
        allowed_markings: list[str] | None = None,
    ) -> tuple[list[Incident], int]:
        conditions = []
        if workspace_id is not None:
            conditions.append(Incident.workspace_id == workspace_id)
        if allowed_markings is not None:
            conditions.append(Incident.classification.in_(allowed_markings))
        if status is not None:
            conditions.append(Incident.status == status)
        total = (
            await self.session.execute(sa.select(sa.func.count(Incident.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            sa.select(Incident)
            .where(*conditions)
            .order_by(Incident.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars()), total

    async def count_open(self) -> int:
        return (
            await self.session.execute(
                sa.select(sa.func.count(Incident.id)).where(
                    Incident.status != IncidentStatus.RESOLVED
                )
            )
        ).scalar_one()

    def add(self, incident: Incident) -> None:
        self.session.add(incident)
