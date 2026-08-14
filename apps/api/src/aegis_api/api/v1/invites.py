"""Public invite redemption (no auth) + platform-level invite creation."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from aegis_api.api.deps import SessionDep, require_roles
from aegis_api.models.user import User
from aegis_api.schemas.access import InviteCreate, InviteCreated, InviteRedeem
from aegis_api.schemas.user import UserRead
from aegis_api.services.invites import InviteService

router = APIRouter(prefix="/invites", tags=["invites"])

PlatformAdmin = Annotated[User, Depends(require_roles())]


@router.post("", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
async def create_platform_invite(
    body: InviteCreate, session: SessionDep, actor: PlatformAdmin
) -> InviteCreated:
    invite, token = await InviteService(session).create(
        email=body.email, role=body.role, actor_id=actor.id, ttl_hours=body.ttl_hours
    )
    from aegis_api.schemas.access import InviteRead

    return InviteCreated(
        **InviteRead.model_validate(invite).model_dump(), token=token
    )  # token shown exactly once


@router.post("/redeem", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def redeem_invite(body: InviteRedeem, session: SessionDep) -> UserRead:
    user = await InviteService(session).redeem(
        token=body.token, password=body.password, full_name=body.full_name
    )
    return UserRead.model_validate(user)
