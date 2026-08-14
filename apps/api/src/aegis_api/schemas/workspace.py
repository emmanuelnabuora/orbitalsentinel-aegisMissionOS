import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_api.models.enums import Role


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=3, max_length=80)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    role: Role


class MemberRoleUpdate(BaseModel):
    role: Role


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    role: Role
    custom_role_id: uuid.UUID | None = None
