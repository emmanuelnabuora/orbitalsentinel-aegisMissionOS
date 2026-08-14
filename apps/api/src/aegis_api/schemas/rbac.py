import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PermissionCatalog(BaseModel):
    permissions: list[str]
    groups: dict[str, list[str]]
    sensitive: list[str]


class CustomRoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    groups: list[str] = Field(min_length=1)


class CustomRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: str
    permission_values: list[str]
    created_at: datetime


class CustomRoleAssign(BaseModel):
    role_slug: str


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    subject_id: uuid.UUID
    payload: dict
    status: str
    requested_by: uuid.UUID
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    reason: str | None
    created_at: datetime


class ApprovalDecision(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=500)
