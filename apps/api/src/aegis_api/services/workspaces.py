"""Workspace lifecycle and membership management (Phase 12).

Lockout guards mirror the platform-role rules: a member cannot demote
themself out of workspace admin, and the last workspace admin cannot be
removed or demoted.
"""

from __future__ import annotations

import re
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import ConflictError, NotFoundError, ValidationFailure
from aegis_api.models.enums import Role
from aegis_api.models.user import User
from aegis_api.models.workspace import Workspace, WorkspaceMembership
from aegis_api.repositories.users import UserRepository
from aegis_api.services.audit import AuditService

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create(self, *, name: str, slug: str, owner: User) -> Workspace:
        if not _SLUG_RE.match(slug):
            raise ValidationFailure("Slug must be lowercase alphanumeric with hyphens")
        exists = (
            await self.session.execute(sa.select(Workspace.id).where(Workspace.slug == slug))
        ).first()
        if exists:
            raise ConflictError("A workspace with this slug already exists")
        ws = Workspace(
            name=name,
            slug=slug,
            members=[WorkspaceMembership(user_id=owner.id, role=Role.ADMIN)],
        )
        self.session.add(ws)
        await self.session.flush()
        self.audit.record(
            actor_id=owner.id,
            action="workspace.created",
            resource_type="workspace",
            resource_id=ws.id,
            detail={"slug": slug},
        )
        await self.session.commit()
        return ws

    async def get_by_slug(self, slug: str) -> Workspace | None:
        return (
            await self.session.execute(sa.select(Workspace).where(Workspace.slug == slug))
        ).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Workspace]:
        stmt = (
            sa.select(Workspace)
            .join(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(Workspace.name)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def membership(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMembership | None:
        return await self.session.get(WorkspaceMembership, (workspace_id, user_id))

    async def add_member(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        actor_id: uuid.UUID,
    ) -> WorkspaceMembership:
        if await UserRepository(self.session).get(user_id) is None:
            raise NotFoundError("User not found")
        if await self.membership(workspace_id, user_id) is not None:
            raise ConflictError("Already a member of this workspace")
        m = WorkspaceMembership(workspace_id=workspace_id, user_id=user_id, role=role)
        self.session.add(m)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="workspace.member_added",
            resource_type="workspace",
            resource_id=workspace_id,
            detail={"user_id": str(user_id), "role": role.value},
        )
        await self.session.commit()
        return m

    async def _admin_count(self, workspace_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                sa.select(sa.func.count())
                .select_from(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.role == Role.ADMIN,
                )
            )
        ).scalar_one()

    async def set_member_role(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        actor_id: uuid.UUID,
    ) -> WorkspaceMembership:
        m = await self.membership(workspace_id, user_id)
        if m is None:
            raise NotFoundError("Membership not found")
        if m.role == Role.ADMIN and role != Role.ADMIN:
            if user_id == actor_id:
                raise ValidationFailure("You cannot demote yourself from workspace admin")
            if await self._admin_count(workspace_id) <= 1:
                raise ValidationFailure("A workspace must retain at least one admin")
        m.role = role
        self.audit.record(
            actor_id=actor_id,
            action="workspace.member_role_changed",
            resource_type="workspace",
            resource_id=workspace_id,
            detail={"user_id": str(user_id), "role": role.value},
        )
        await self.session.commit()
        return m

    async def remove_member(
        self, *, workspace_id: uuid.UUID, user_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        m = await self.membership(workspace_id, user_id)
        if m is None:
            raise NotFoundError("Membership not found")
        if m.role == Role.ADMIN and await self._admin_count(workspace_id) <= 1:
            raise ValidationFailure("A workspace must retain at least one admin")
        await self.session.delete(m)
        self.audit.record(
            actor_id=actor_id,
            action="workspace.member_removed",
            resource_type="workspace",
            resource_id=workspace_id,
            detail={"user_id": str(user_id)},
        )
        await self.session.commit()
