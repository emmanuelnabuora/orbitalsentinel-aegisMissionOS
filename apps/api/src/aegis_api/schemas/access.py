import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from aegis_api.models.enums import Role


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role
    ttl_hours: int = Field(default=72, ge=1, le=720)


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: Role
    expires_at: datetime
    used_at: datetime | None


class InviteCreated(InviteRead):
    token: str  # shown exactly once


class InviteRedeem(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=12, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)


class ServiceAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: Role = Role.OPERATOR


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    key: str  # full key, shown exactly once
