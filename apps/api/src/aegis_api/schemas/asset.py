import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import AssetStatus, AssetType, Criticality


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    asset_type: AssetType
    status: AssetStatus = AssetStatus.UNKNOWN
    criticality: Criticality
    attributes: dict = Field(default_factory=dict)
    classification: str = Field(default="unclassified", pattern="^(unclassified|cui|secret)$")


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: AssetStatus | None = None
    criticality: Criticality | None = None
    attributes: dict | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    classification: str
    name: str
    description: str | None
    asset_type: AssetType
    status: AssetStatus
    criticality: Criticality
    attributes: dict
    created_at: datetime
    updated_at: datetime


class AssetDependencyCreate(BaseModel):
    depends_on_id: uuid.UUID
    criticality: Criticality = Criticality.MEDIUM
