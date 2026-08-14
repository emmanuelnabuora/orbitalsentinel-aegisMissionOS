import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from aegis_api.api.deps import SessionDep, require_roles
from aegis_api.core.abac import Classification
from aegis_api.core.exceptions import NotFoundError
from aegis_api.models.enums import Role
from aegis_api.models.user import User
from aegis_api.schemas.common import Page
from aegis_api.schemas.user import UserCreate, UserRead
from aegis_api.services.audit import AuditService
from aegis_api.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])

AdminUser = Annotated[User, Depends(require_roles())]  # admin-only (admin always passes)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, session: SessionDep, actor: AdminUser) -> UserRead:
    user = await UserService(session).create(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        roles=body.roles,
        actor_id=actor.id,
    )
    return UserRead.model_validate(user)


@router.get("", response_model=Page[UserRead])
async def list_users(
    session: SessionDep,
    _: AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserRead]:
    users, total = await UserService(session).list(limit=limit, offset=offset)
    return Page(
        items=[UserRead.model_validate(u) for u in users], total=total, limit=limit, offset=offset
    )


# -- platform role management (Phase 20) -------------------------------------


class RolesUpdate(BaseModel):
    roles: list[Role]


@router.put("/{user_id}/roles", response_model=UserRead)
async def set_user_roles(
    user_id: uuid.UUID, body: RolesUpdate, session: SessionDep, actor: AdminUser
) -> UserRead:
    user = await UserService(session).set_roles(
        user_id=user_id, roles=body.roles, actor_id=actor.id
    )
    return UserRead.model_validate(user)


# -- clearance management (Phase 17, ABAC) -----------------------------------


class ClearanceUpdate(BaseModel):
    clearance: Classification


@router.put("/{user_id}/clearance", response_model=UserRead)
async def set_clearance(
    user_id: uuid.UUID, body: ClearanceUpdate, session: SessionDep, actor: AdminUser
) -> UserRead:
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found")
    target.clearance = body.clearance.value
    AuditService(session).record(
        actor_id=actor.id,
        action="user.clearance_changed",
        resource_type="user",
        resource_id=target.id,
        detail={"clearance": body.clearance.value},
    )
    await session.commit()
    await session.refresh(target)
    return UserRead.model_validate(target)
