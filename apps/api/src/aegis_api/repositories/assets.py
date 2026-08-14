from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.asset import Asset, AssetDependency
from aegis_api.models.enums import AssetStatus, AssetType, Criticality


class AssetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, asset_id: uuid.UUID) -> Asset | None:
        return await self.session.get(Asset, asset_id)

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        workspace_id: uuid.UUID | None = None,
        allowed_markings: list[str] | None = None,
        asset_type: AssetType | None = None,
        status: AssetStatus | None = None,
        criticality: Criticality | None = None,
        search: str | None = None,
    ) -> tuple[list[Asset], int]:
        conditions = []
        if workspace_id is not None:
            conditions.append(Asset.workspace_id == workspace_id)
        if allowed_markings is not None:
            conditions.append(Asset.classification.in_(allowed_markings))
        if asset_type is not None:
            conditions.append(Asset.asset_type == asset_type)
        if status is not None:
            conditions.append(Asset.status == status)
        if criticality is not None:
            conditions.append(Asset.criticality == criticality)
        if search:
            conditions.append(Asset.name.ilike(f"%{search}%"))

        total = (
            await self.session.execute(sa.select(sa.func.count(Asset.id)).where(*conditions))
        ).scalar_one()
        stmt = (
            sa.select(Asset)
            .where(*conditions)
            .order_by(Asset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars()), total

    def add(self, asset: Asset) -> None:
        self.session.add(asset)

    async def delete(self, asset: Asset) -> None:
        await self.session.delete(asset)

    async def get_dependency(
        self, asset_id: uuid.UUID, depends_on_id: uuid.UUID
    ) -> AssetDependency | None:
        return await self.session.get(AssetDependency, (asset_id, depends_on_id))

    async def dependencies_among(self, asset_ids: set[uuid.UUID]) -> list[AssetDependency]:
        """Dependency edges where both endpoints are in the given set."""
        if not asset_ids:
            return []
        stmt = sa.select(AssetDependency).where(
            AssetDependency.asset_id.in_(asset_ids),
            AssetDependency.depends_on_id.in_(asset_ids),
        )
        return list((await self.session.execute(stmt)).scalars())
