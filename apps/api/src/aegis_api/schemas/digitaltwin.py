"""Digital Twin schemas: scenario perturbations and projected impact.

A scenario is an ephemeral what-if: a named set of perturbations applied to a
read-only projection of live state. Nothing here is persisted — the twin
answers "what would happen if…" without changing anything.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis_api.models.enums import AssetStatus


class PerturbationKind(StrEnum):
    SET_STATUS = "set_status"  # set an asset to an explicit status
    OFFLINE = "offline"  # shorthand: force OFFLINE
    ADD_ALERTS = "add_alerts"  # add N open alerts to an asset
    REMOVE_ASSET = "remove_asset"  # simulate total loss (drops from missions)


class Perturbation(BaseModel):
    kind: PerturbationKind
    asset_id: uuid.UUID
    status: AssetStatus | None = None  # required for SET_STATUS
    magnitude: int = Field(default=1, ge=0, le=50)  # used by ADD_ALERTS

    @model_validator(mode="after")
    def _check(self) -> "Perturbation":
        if self.kind == PerturbationKind.SET_STATUS and self.status is None:
            raise ValueError("set_status perturbation requires a status")
        return self


class ScenarioSimulate(BaseModel):
    name: str = Field(default="scenario", max_length=200)
    perturbations: list[Perturbation] = Field(default_factory=list)


class ImpactedAsset(BaseModel):
    asset_id: uuid.UUID
    name: str
    baseline_status: str
    projected_status: str
    removed: bool
    added_alerts: int


class MissionProjection(BaseModel):
    mission_id: uuid.UUID
    name: str
    baseline_score: int
    projected_score: int
    delta: int  # projected - baseline (negative = worse)
    baseline_health: str
    projected_health: str
    crossed_threshold: bool
    projected_factors: list[str]


class SimulationResult(BaseModel):
    scenario_name: str
    baseline_average: int
    projected_average: int
    average_delta: int
    missions_at_risk_before: int
    missions_at_risk_after: int
    newly_at_risk: list[str]
    impacted_assets: list[ImpactedAsset]
    missions: list[MissionProjection]
    summary: str


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    perturbations: list[Perturbation] = Field(default_factory=list)


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    perturbations: list[dict]
    created_by: uuid.UUID | None
    last_run_at: datetime | None
    created_at: datetime
