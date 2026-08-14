import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import AlertSeverity, IndicatorType, ThreatCategory


class IndicatorCreate(BaseModel):
    indicator_type: IndicatorType
    value: str = Field(min_length=1, max_length=500)
    category: ThreatCategory = ThreatCategory.UNKNOWN
    severity: AlertSeverity
    confidence: int = Field(default=50, ge=0, le=100)
    source: str = Field(default="manual", max_length=100)
    description: str | None = None


class IndicatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    indicator_type: IndicatorType
    value: str
    category: ThreatCategory
    severity: AlertSeverity
    confidence: int
    source: str
    description: str | None
    active: bool
    first_seen: datetime
    last_seen: datetime


class ThreatMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    indicator_id: uuid.UUID
    asset_id: uuid.UUID
    alert_id: uuid.UUID | None
    matched_on: str
    created_at: datetime
    indicator_value: str | None = None
    indicator_category: ThreatCategory | None = None
    severity: AlertSeverity | None = None
    asset_name: str | None = None


class IngestResult(BaseModel):
    source: str
    received: int
    created: int
    updated: int


class CorrelationResult(BaseModel):
    indicators_checked: int
    assets_checked: int
    new_matches: int
    alerts_raised: int
    matches: list[ThreatMatchRead]


class ThreatIntelSummary(BaseModel):
    active_indicators: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    total_matches: int
    sources: dict[str, int]
    last_ingest: datetime | None
