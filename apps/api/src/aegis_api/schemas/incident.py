import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import AlertSeverity, IncidentStatus
from aegis_api.schemas.alert import AlertRead


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str | None = None
    severity: AlertSeverity
    alert_ids: list[uuid.UUID] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    status: IncidentStatus | None = None
    summary: str | None = None
    commander_id: uuid.UUID | None = None


class IncidentNote(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class IncidentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    at: datetime
    kind: str
    message: str
    actor_id: uuid.UUID | None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str | None
    severity: AlertSeverity
    status: IncidentStatus
    commander_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class IncidentDetail(IncidentRead):
    events: list[IncidentEventRead]
    alerts: list[AlertRead]
