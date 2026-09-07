"""Typed schemas for external source payloads and normalized drafts."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from aegis_api.models.enums import AlertSeverity


class GPRecord(BaseModel):
    """One object from Celestrak's GP catalog (OMM JSON format)."""

    object_name: str = Field(alias="OBJECT_NAME")
    object_id: str = Field(alias="OBJECT_ID")  # international designator
    norad_cat_id: int = Field(alias="NORAD_CAT_ID")
    epoch: datetime = Field(alias="EPOCH")
    mean_motion: float = Field(alias="MEAN_MOTION")  # rev/day
    eccentricity: float = Field(alias="ECCENTRICITY")
    inclination: float = Field(alias="INCLINATION")  # deg
    ra_of_asc_node: float = Field(alias="RA_OF_ASC_NODE")
    arg_of_pericenter: float = Field(alias="ARG_OF_PERICENTER")
    mean_anomaly: float = Field(alias="MEAN_ANOMALY")
    bstar: float = Field(alias="BSTAR", default=0.0)

    model_config = {"populate_by_name": True}

    @field_validator("epoch", mode="after")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    @property
    def approx_period_minutes(self) -> float:
        return 1440.0 / self.mean_motion if self.mean_motion else 0.0


class KpReading(BaseModel):
    time_tag: datetime
    kp_index: float

    @field_validator("time_tag", mode="after")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class SolarWindSummary(BaseModel):
    time_tag: datetime
    wind_speed_km_s: float | None = None
    bt_nt: float | None = None
    bz_nt: float | None = None

    @field_validator("time_tag", mode="after")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class SwpcBulletin(BaseModel):
    product_id: str
    issue_datetime: datetime
    message: str

    @field_validator("issue_datetime", mode="after")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class ConjunctionRecord(BaseModel):
    """One SOCRATES close-approach row."""

    norad_cat_id_1: int
    object_name_1: str
    norad_cat_id_2: int
    object_name_2: str
    tca: datetime  # time of closest approach (UTC)
    min_range_km: float
    relative_speed_km_s: float
    max_probability: float

    @field_validator("tca", mode="after")
    @classmethod
    def _tca_utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class AlertDraft(BaseModel):
    """Normalized alert candidate. dedupe_key is a stable natural key so
    repeated polls of the same upstream event never duplicate alerts."""

    source: str  # "swpc" | "celestrak"
    dedupe_key: str
    severity: AlertSeverity
    title: str
    body: str
    observed_at: datetime
    metadata: dict = Field(default_factory=dict)
