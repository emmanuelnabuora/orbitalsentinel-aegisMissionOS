import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import ConflictError, NotFoundError
from aegis_api.models.mission import Mission, MissionAsset
from aegis_api.repositories.assets import AssetRepository
from aegis_api.repositories.missions import MissionRepository
from aegis_api.schemas.mission import (
    GraphEdge,
    GraphNode,
    MissionAssetAttach,
    MissionCreate,
    MissionGraph,
    MissionUpdate,
)
from aegis_api.services.audit import AuditService


class MissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MissionRepository(session)
        self.assets = AssetRepository(session)
        self.audit = AuditService(session)

    async def get(self, mission_id: uuid.UUID) -> Mission:
        mission = await self.repo.get(mission_id)
        if mission is None:
            raise NotFoundError("Mission not found")
        return mission

    async def create(
        self, data: MissionCreate, *, actor_id: uuid.UUID, workspace_id: uuid.UUID | None = None
    ) -> Mission:
        mission = Mission(**data.model_dump(), owner_id=actor_id, workspace_id=workspace_id)
        self.repo.add(mission)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="mission.created",
            resource_type="mission",
            resource_id=mission.id,
        )
        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def update(
        self, mission_id: uuid.UUID, data: MissionUpdate, *, actor_id: uuid.UUID
    ) -> Mission:
        mission = await self.get(mission_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(mission, field, value)
        self.audit.record(
            actor_id=actor_id,
            action="mission.updated",
            resource_type="mission",
            resource_id=mission.id,
            detail={"fields": sorted(changes)},
        )
        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def delete(self, mission_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        mission = await self.get(mission_id)
        await self.repo.delete(mission)
        self.audit.record(
            actor_id=actor_id,
            action="mission.deleted",
            resource_type="mission",
            resource_id=mission_id,
        )
        await self.session.commit()

    async def attach_asset(
        self, mission_id: uuid.UUID, data: MissionAssetAttach, *, actor_id: uuid.UUID
    ) -> Mission:
        mission = await self.get(mission_id)
        if await self.assets.get(data.asset_id) is None:
            raise NotFoundError("Asset not found")
        if await self.repo.get_link(mission_id, data.asset_id) is not None:
            raise ConflictError("Asset is already attached to this mission")
        self.session.add(
            MissionAsset(
                mission_id=mission_id,
                asset_id=data.asset_id,
                dependency_criticality=data.dependency_criticality,
            )
        )
        self.audit.record(
            actor_id=actor_id,
            action="mission.asset_attached",
            resource_type="mission",
            resource_id=mission_id,
            detail={"asset_id": str(data.asset_id)},
        )
        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def detach_asset(
        self, mission_id: uuid.UUID, asset_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        link = await self.repo.get_link(mission_id, asset_id)
        if link is None:
            raise NotFoundError("Asset is not attached to this mission")
        await self.session.delete(link)
        self.audit.record(
            actor_id=actor_id,
            action="mission.asset_detached",
            resource_type="mission",
            resource_id=mission_id,
            detail={"asset_id": str(asset_id)},
        )
        await self.session.commit()

    async def graph(self, mission_id: uuid.UUID) -> MissionGraph:
        """Mission dependency graph: mission -> assets, plus asset -> asset
        edges among that mission's assets. Feeds MissionIQ and Digital Twin."""
        mission = await self.get(mission_id)
        nodes = [
            GraphNode(
                id=str(mission.id),
                kind="mission",
                label=mission.name,
                status=mission.status.value,
                criticality=mission.priority.value,
            )
        ]
        edges: list[GraphEdge] = []
        asset_ids: set[uuid.UUID] = set()

        for link in mission.asset_links:
            asset = link.asset
            asset_ids.add(asset.id)
            nodes.append(
                GraphNode(
                    id=str(asset.id),
                    kind="asset",
                    label=asset.name,
                    status=asset.status.value,
                    criticality=asset.criticality.value,
                )
            )
            edges.append(
                GraphEdge(
                    source=str(mission.id),
                    target=str(asset.id),
                    kind="mission_dependency",
                    criticality=link.dependency_criticality.value,
                )
            )

        for dep in await self.assets.dependencies_among(asset_ids):
            edges.append(
                GraphEdge(
                    source=str(dep.asset_id),
                    target=str(dep.depends_on_id),
                    kind="asset_dependency",
                    criticality=dep.criticality.value,
                )
            )

        return MissionGraph(nodes=nodes, edges=edges)
