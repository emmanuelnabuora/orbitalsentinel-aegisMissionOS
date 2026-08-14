import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    severity: AlertSeverity
    source: str = Field(default="manual", max_length=100)
    asset_id: uuid.UUID | None = None
    classification: str = Field(default="unclassified", pattern="^(unclassified|cui|secret)$")


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    assigned_to: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    classification: str
    title: str
    description: str | None
    severity: AlertSeverity
    status: AlertStatus
    source: str
    asset_id: uuid.UUID | None
    asset_name: str | None = None
    assigned_to: uuid.UUID | None
    incident_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
