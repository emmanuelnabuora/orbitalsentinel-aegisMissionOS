import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from aegis_api.models.enums import Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    roles: list[Role] = Field(min_length=1)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    roles: list[Role]
    is_active: bool
    is_service_account: bool = False
    clearance: str = "unclassified"
    mfa_enabled: bool = False
    created_at: datetime
