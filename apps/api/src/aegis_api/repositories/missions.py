from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.enums import MissionStatus
from aegis_api.models.mission import Mission, MissionAsset


class MissionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, mission_id: uuid.UUID) -> Mission | None:
        return await self.session.get(Mission, mission_id)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: MissionStatus | None = None,
        workspace_id: uuid.UUID | None = None,
        allowed_markings: list[str] | None = None,
    ) -> tuple[list[Mission], int]:
        conditions = []
        if workspace_id is not None:
            conditions.append(Mission.workspace_id == workspace_id)
        if allowed_markings is not None:
            conditions.append(Mission.classification.in_(allowed_markings))
        if status is not None:
            conditions.append(Mission.status == status)
        total = (
            await self.session.execute(sa.select(sa.func.count(Mission.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            sa.select(Mission)
            .where(*conditions)
            .order_by(Mission.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars()), total

    def add(self, mission: Mission) -> None:
        self.session.add(mission)

    async def delete(self, mission: Mission) -> None:
        await self.session.delete(mission)

    async def get_link(self, mission_id: uuid.UUID, asset_id: uuid.UUID) -> MissionAsset | None:
        return await self.session.get(MissionAsset, (mission_id, asset_id))
