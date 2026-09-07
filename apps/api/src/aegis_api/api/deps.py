"""FastAPI dependencies: session, current user, role enforcement."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.db import get_session
from aegis_api.core.security import TokenError, decode_access_token
from aegis_api.models.enums import Role
from aegis_api.models.user import User
from aegis_api.models.workspace import Workspace
from aegis_api.repositories.users import UserRepository

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


async def get_current_user(
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if creds is None and x_api_key is not None:
        # Programmatic access: API key resolves to a service account.
        from aegis_api.services.apikeys import ApiKeyService

        account = await ApiKeyService(session).authenticate(x_api_key)
        if account is None:
            raise _unauthorized("Invalid or expired token")
        return account
    if creds is None:
        raise _unauthorized()
    try:
        claims = decode_access_token(creds.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (TokenError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_workspace(
    session: SessionDep,
    user: CurrentUser,
    x_workspace: Annotated[str | None, Header(alias="X-Workspace")] = None,
) -> Workspace | None:
    """Resolve the active workspace from the X-Workspace header (slug).

    Absent header -> None (legacy single-tenant behavior). Present header
    requires the caller to be a member; platform admins pass regardless.
    One generic 404 for unknown-slug and not-a-member (no enumeration).
    """
    if x_workspace is None:
        return None
    from aegis_api.services.workspaces import WorkspaceService

    svc = WorkspaceService(session)
    ws = await svc.get_by_slug(x_workspace)
    if ws is not None:
        if Role.ADMIN in set(user.roles):
            return ws
        if await svc.membership(ws.id, user.id) is not None:
            return ws
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")


WorkspaceDep = Annotated[Workspace | None, Depends(get_workspace)]


def require_permission(perm):
    """Permission-based gate (Phase 13/14).

    Effective permissions = platform roles ∪ workspace grant when an
    X-Workspace header is active. A membership with a custom role uses
    the custom role's permission set in place of the built-in role's.
    """
    from aegis_api.core.permissions import (
        ROLE_PERMISSIONS,
        Permission,
        has_permission,
    )

    if not isinstance(perm, Permission):
        raise TypeError(f"Expected Permission, got {type(perm).__name__}")

    async def _check(
        session: SessionDep,
        user: CurrentUser,
        ws: "WorkspaceDep",
    ) -> User:
        if has_permission(list(user.roles), perm):
            return user
        if ws is not None:
            from aegis_api.models.workspace import WorkspaceMembership
            from aegis_api.services.rbac import effective_custom_permissions

            membership = await session.get(WorkspaceMembership, (ws.id, user.id))
            if membership is not None:
                if membership.custom_role_id is not None:
                    from aegis_api.models.rbac import CustomRole

                    role = await session.get(CustomRole, membership.custom_role_id)
                    if perm in effective_custom_permissions(role):
                        return user
                elif perm in ROLE_PERMISSIONS.get(membership.role, frozenset()):
                    return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")

    return _check


def require_roles(*allowed: Role):
    """Authorize if the user holds any allowed role. Admin always passes."""

    async def checker(user: CurrentUser) -> User:
        roles = set(user.roles)
        if Role.ADMIN in roles or roles & set(allowed):
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient privileges")

    return checker
