import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import Criticality, MissionStatus
from aegis_api.schemas.asset import AssetRead


class MissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: MissionStatus = MissionStatus.PLANNING
    priority: Criticality


class MissionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: MissionStatus | None = None
    priority: Criticality | None = None


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: MissionStatus
    priority: Criticality
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class MissionAssetAttach(BaseModel):
    asset_id: uuid.UUID
    dependency_criticality: Criticality = Criticality.MEDIUM


class MissionAssetRead(BaseModel):
    asset: AssetRead
    dependency_criticality: Criticality


class GraphNode(BaseModel):
    id: str
    kind: str  # "mission" | "asset"
    label: str
    status: str | None = None
    criticality: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str  # "mission_dependency" | "asset_dependency"
    criticality: str


class MissionGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
