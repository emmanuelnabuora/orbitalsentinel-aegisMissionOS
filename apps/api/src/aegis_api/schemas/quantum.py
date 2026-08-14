import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import CryptoKind


class CryptoRecordCreate(BaseModel):
    asset_id: uuid.UUID
    kind: CryptoKind
    algorithm: str = Field(min_length=1, max_length=50)
    key_size: int | None = Field(default=None, ge=1)
    subject: str | None = Field(default=None, max_length=300)
    expires_at: datetime | None = None


class CryptoRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    asset_name: str | None = None
    kind: CryptoKind
    algorithm: str
    key_size: int | None
    subject: str | None
    expires_at: datetime | None
    pqc_ready: bool
    created_at: datetime


class QuantumReadiness(BaseModel):
    score: int  # 0-100
    total_records: int
    pqc_ready_records: int
    vulnerable_records: int
    vulnerable_by_algorithm: dict[str, int]
    exposed_assets: list[str]  # names of assets with vulnerable crypto
    recommendations: list[str]
