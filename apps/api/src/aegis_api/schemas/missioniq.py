import uuid

from pydantic import BaseModel

from aegis_api.models.enums import MissionStatus


class MissionAssurance(BaseModel):
    mission_id: uuid.UUID
    name: str
    status: MissionStatus
    score: int  # 0-100
    health: str  # assured | degraded | at_risk
    asset_count: int
    degraded_assets: int
    offline_assets: int
    open_alerts: int
    factors: list[str]  # human-readable explanation (Explainable AI principle)


class FleetSummary(BaseModel):
    average_score: int
    threat_level: str  # low | elevated | high | severe
    missions: list[MissionAssurance]
    total_assets: int
    open_alerts: int
    open_incidents: int
