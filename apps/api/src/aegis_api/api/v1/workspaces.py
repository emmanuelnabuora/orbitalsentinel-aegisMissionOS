"""Workspace lifecycle, membership, invites, and service accounts."""

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status

from aegis_api.api.deps import CurrentUser, SessionDep, require_roles
from aegis_api.core.permissions import (
    PERMISSION_GROUPS,
    SENSITIVE_PERMISSIONS,
    Permission,
)
from aegis_api.models.access import ApiKey
from aegis_api.models.enums import Role
from aegis_api.models.user import User
from aegis_api.models.workspace import Workspace, WorkspaceMembership
from aegis_api.repositories.users import UserRepository
from aegis_api.schemas.access import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
    InviteCreate,
    InviteCreated,
    ServiceAccountCreate,
    ServiceAccountRead,
)
from aegis_api.schemas.rbac import (
    ApprovalDecision,
    ApprovalRead,
    CustomRoleAssign,
    CustomRoleCreate,
    CustomRoleRead,
    PermissionCatalog,
)
from aegis_api.schemas.user import UserRead
from aegis_api.schemas.workspace import (
    MemberAdd,
    MemberRead,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceRead,
)
from aegis_api.services.apikeys import ApiKeyService, ServiceAccountService
from aegis_api.services.invites import InviteService
from aegis_api.services.rbac import ApprovalService, CustomRoleService
from aegis_api.services.workspaces import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

PlatformAdmin = Annotated[User, Depends(require_roles())]


async def _require_ws_admin(session: SessionDep, user: CurrentUser, slug: str) -> Workspace:
    """Workspace admin (or platform admin) gate. Generic 404 otherwise."""
    svc = WorkspaceService(session)
    ws = await svc.get_by_slug(slug)
    if ws is not None:
        if Role.ADMIN in set(user.roles):
            return ws
        m = await svc.membership(ws.id, user.id)
        if m is not None and m.role == Role.ADMIN:
            return ws
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreate, session: SessionDep, actor: PlatformAdmin
) -> WorkspaceRead:
    ws = await WorkspaceService(session).create(name=body.name, slug=body.slug, owner=actor)
    return WorkspaceRead.model_validate(ws)


@router.get("", response_model=list[WorkspaceRead])
async def my_workspaces(session: SessionDep, user: CurrentUser) -> list[WorkspaceRead]:
    ws = await WorkspaceService(session).list_for_user(user.id)
    return [WorkspaceRead.model_validate(w) for w in ws]


@router.get("/{slug}/members", response_model=list[MemberRead])
async def list_members(slug: str, session: SessionDep, user: CurrentUser) -> list[MemberRead]:
    svc = WorkspaceService(session)
    ws = await svc.get_by_slug(slug)
    if ws is None or (
        Role.ADMIN not in set(user.roles) and await svc.membership(ws.id, user.id) is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return [MemberRead.model_validate(m) for m in ws.members]


@router.post("/{slug}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
async def add_member(
    slug: str, body: MemberAdd, session: SessionDep, user: CurrentUser
) -> MemberRead:
    ws = await _require_ws_admin(session, user, slug)
    m = await WorkspaceService(session).add_member(
        workspace_id=ws.id, user_id=body.user_id, role=body.role, actor_id=user.id
    )
    return MemberRead.model_validate(m)


@router.put("/{slug}/members/{user_id}", response_model=MemberRead)
async def set_member_role(
    slug: str,
    user_id: uuid.UUID,
    body: MemberRoleUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> MemberRead:
    ws = await _require_ws_admin(session, user, slug)
    m = await WorkspaceService(session).set_member_role(
        workspace_id=ws.id, user_id=user_id, role=body.role, actor_id=user.id
    )
    return MemberRead.model_validate(m)


@router.delete("/{slug}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    slug: str, user_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    ws = await _require_ws_admin(session, user, slug)
    await WorkspaceService(session).remove_member(
        workspace_id=ws.id, user_id=user_id, actor_id=user.id
    )


# -- invites ----------------------------------------------------------------


@router.post("/{slug}/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
async def create_invite(
    slug: str, body: InviteCreate, session: SessionDep, user: CurrentUser
) -> InviteCreated:
    ws = await _require_ws_admin(session, user, slug)
    invite, token = await InviteService(session).create(
        email=body.email,
        role=body.role,
        actor_id=user.id,
        ttl_hours=body.ttl_hours,
        workspace_id=ws.id,
    )
    from aegis_api.schemas.access import InviteRead

    return InviteCreated(
        **InviteRead.model_validate(invite).model_dump(), token=token
    )  # token shown exactly once


# -- service accounts + API keys -------------------------------------------


async def _require_ws_service_account(
    session: SessionDep, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> User:
    """Confirm account_id is a service account AND a member of this workspace.

    Tenant-isolation gate: without this, an admin of workspace A could
    mint or revoke keys belonging to workspace B's service accounts by
    supplying an account_id/key_id they'd obtained or guessed, since
    _require_ws_admin alone only proves admin standing in *some*
    workspace named `slug` — it says nothing about the target account.
    """
    account = await UserRepository(session).get(account_id)
    if account is None or not account.is_service_account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service account not found")
    membership = (
        await session.execute(
            sa.select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == account_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service account not found")
    return account


@router.get(
    "/{slug}/service-accounts",
    response_model=list[ServiceAccountRead],
)
async def list_service_accounts(
    slug: str, session: SessionDep, user: CurrentUser
) -> list[ServiceAccountRead]:
    ws = await _require_ws_admin(session, user, slug)
    pairs = await ServiceAccountService(session).list_for_workspace(ws.id)
    return [
        ServiceAccountRead(
            id=account.id,
            email=account.email,
            full_name=account.full_name,
            created_at=account.created_at,
            keys=[ApiKeyRead.model_validate(k) for k in keys],
        )
        for account, keys in pairs
    ]


@router.post(
    "/{slug}/service-accounts",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_account(
    slug: str, body: ServiceAccountCreate, session: SessionDep, user: CurrentUser
) -> UserRead:
    ws = await _require_ws_admin(session, user, slug)
    account = await ServiceAccountService(session).create(
        name=body.name,
        email=body.email,
        role=body.role,
        actor_id=user.id,
        workspace_id=ws.id,
    )
    return UserRead.model_validate(account)


@router.post(
    "/{slug}/service-accounts/{account_id}/keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def mint_api_key(
    slug: str,
    account_id: uuid.UUID,
    body: ApiKeyCreate,
    session: SessionDep,
    user: CurrentUser,
) -> ApiKeyCreated:
    ws = await _require_ws_admin(session, user, slug)
    await _require_ws_service_account(session, ws.id, account_id)
    key, raw = await ApiKeyService(session).mint(
        account_id=account_id, name=body.name, actor_id=user.id
    )

    return ApiKeyCreated(
        **ApiKeyRead.model_validate(key).model_dump(), key=raw
    )  # key shown exactly once


@router.delete("/{slug}/service-accounts/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    slug: str, key_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    ws = await _require_ws_admin(session, user, slug)
    key = await session.get(ApiKey, key_id)
    if key is None or key.revoked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await _require_ws_service_account(session, ws.id, key.user_id)
    await ApiKeyService(session).revoke(key_id=key_id, actor_id=user.id)


# -- custom roles + approvals (Phase 14) ------------------------------------


@router.get("/rbac/catalog", response_model=PermissionCatalog)
async def permission_catalog(_: CurrentUser) -> PermissionCatalog:
    return PermissionCatalog(
        permissions=[p.value for p in Permission],
        groups={k: sorted(p.value for p in v) for k, v in PERMISSION_GROUPS.items()},
        sensitive=sorted(p.value for p in SENSITIVE_PERMISSIONS),
    )


@router.get("/{slug}/roles", response_model=list[CustomRoleRead])
async def list_custom_roles(
    slug: str, session: SessionDep, user: CurrentUser
) -> list[CustomRoleRead]:
    ws = await _require_ws_admin(session, user, slug)
    roles = await CustomRoleService(session).list(ws.id)
    return [CustomRoleRead.model_validate(r) for r in roles]


@router.post("/{slug}/roles", response_model=CustomRoleRead, status_code=status.HTTP_201_CREATED)
async def create_custom_role(
    slug: str, body: CustomRoleCreate, session: SessionDep, user: CurrentUser
) -> CustomRoleRead:
    ws = await _require_ws_admin(session, user, slug)
    role, _approval = await CustomRoleService(session).create(
        workspace_id=ws.id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        groups=body.groups,
        actor_id=user.id,
    )
    return CustomRoleRead.model_validate(role)


@router.put("/{slug}/members/{user_id}/custom-role", status_code=status.HTTP_204_NO_CONTENT)
async def assign_custom_role(
    slug: str,
    user_id: uuid.UUID,
    body: CustomRoleAssign,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    ws = await _require_ws_admin(session, user, slug)
    await CustomRoleService(session).assign(
        workspace_id=ws.id, user_id=user_id, role_slug=body.role_slug, actor_id=user.id
    )


@router.delete("/{slug}/members/{user_id}/custom-role", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_custom_role(
    slug: str, user_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    ws = await _require_ws_admin(session, user, slug)
    await CustomRoleService(session).unassign(workspace_id=ws.id, user_id=user_id, actor_id=user.id)


@router.get("/{slug}/approvals", response_model=list[ApprovalRead])
async def pending_approvals(
    slug: str, session: SessionDep, user: CurrentUser
) -> list[ApprovalRead]:
    ws = await _require_ws_admin(session, user, slug)
    items = await ApprovalService(session).list_pending(ws.id)
    return [ApprovalRead.model_validate(a) for a in items]


@router.post("/{slug}/approvals/{approval_id}", response_model=ApprovalRead)
async def decide_approval(
    slug: str,
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    session: SessionDep,
    user: CurrentUser,
) -> ApprovalRead:
    ws = await _require_ws_admin(session, user, slug)
    approval = await ApprovalService(session).decide(
        approval_id=approval_id,
        workspace_id=ws.id,
        approve=body.approve,
        reason=body.reason,
        actor_id=user.id,
    )
    return ApprovalRead.model_validate(approval)
