import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import ConflictError, NotFoundError, ValidationFailure
from aegis_api.models.asset import Asset, AssetDependency
from aegis_api.repositories.assets import AssetRepository
from aegis_api.schemas.asset import AssetCreate, AssetDependencyCreate, AssetUpdate
from aegis_api.services.audit import AuditService


class AssetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AssetRepository(session)
        self.audit = AuditService(session)

    async def get(self, asset_id: uuid.UUID) -> Asset:
        asset = await self.repo.get(asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")
        return asset

    async def create(
        self, data: AssetCreate, *, actor_id: uuid.UUID, workspace_id: uuid.UUID | None = None
    ) -> Asset:
        asset = Asset(**data.model_dump(), workspace_id=workspace_id)
        self.repo.add(asset)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id, action="asset.created", resource_type="asset", resource_id=asset.id
        )
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def update(self, asset_id: uuid.UUID, data: AssetUpdate, *, actor_id: uuid.UUID) -> Asset:
        asset = await self.get(asset_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(asset, field, value)
        self.audit.record(
            actor_id=actor_id,
            action="asset.updated",
            resource_type="asset",
            resource_id=asset.id,
            detail={"fields": sorted(changes)},
        )
        await self.session.commit()
        await self.session.refresh(asset)
        return asset

    async def delete(self, asset_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        asset = await self.get(asset_id)
        await self.repo.delete(asset)
        self.audit.record(
            actor_id=actor_id, action="asset.deleted", resource_type="asset", resource_id=asset_id
        )
        await self.session.commit()

    async def add_dependency(
        self, asset_id: uuid.UUID, data: AssetDependencyCreate, *, actor_id: uuid.UUID
    ) -> None:
        if asset_id == data.depends_on_id:
            raise ValidationFailure("An asset cannot depend on itself")
        await self.get(asset_id)
        await self.get(data.depends_on_id)
        if await self.repo.get_dependency(asset_id, data.depends_on_id) is not None:
            raise ConflictError("Dependency already exists")
        self.session.add(
            AssetDependency(
                asset_id=asset_id, depends_on_id=data.depends_on_id, criticality=data.criticality
            )
        )
        self.audit.record(
            actor_id=actor_id,
            action="asset.dependency_added",
            resource_type="asset",
            resource_id=asset_id,
            detail={"depends_on": str(data.depends_on_id)},
        )
        await self.session.commit()
