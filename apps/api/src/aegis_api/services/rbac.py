"""Custom roles and approval workflows (Phase 14).

Separation of duties: a custom role containing any SENSITIVE_PERMISSIONS
is created in "pending" status alongside an ApprovalRequest, and only a
*different* workspace admin can approve it. Self-approval is refused.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import ConflictError, NotFoundError, ValidationFailure
from aegis_api.core.permissions import (
    SENSITIVE_PERMISSIONS,
    Permission,
    resolve_groups,
)
from aegis_api.models.rbac import ApprovalRequest, CustomRole, CustomRolePermission
from aegis_api.models.workspace import WorkspaceMembership
from aegis_api.services.audit import AuditService
from aegis_api.services.notifications import NotificationService

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class CustomRoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def list(self, workspace_id: uuid.UUID) -> list[CustomRole]:
        stmt = (
            sa.select(CustomRole)
            .where(CustomRole.workspace_id == workspace_id)
            .order_by(CustomRole.name)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_slug(self, workspace_id: uuid.UUID, slug: str) -> CustomRole | None:
        stmt = sa.select(CustomRole).where(
            CustomRole.workspace_id == workspace_id, CustomRole.slug == slug
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        name: str,
        slug: str,
        description: str | None,
        groups: list[str],
        actor_id: uuid.UUID,
    ) -> tuple[CustomRole, ApprovalRequest | None]:
        if not _SLUG_RE.match(slug):
            raise ValidationFailure("Slug must be lowercase alphanumeric with hyphens")
        try:
            perms = resolve_groups(groups)
        except KeyError as exc:
            raise ValidationFailure(f"Unknown permission group: {exc.args[0]}") from exc
        if not perms:
            raise ValidationFailure("A role needs at least one permission group")
        if await self.get_by_slug(workspace_id, slug) is not None:
            raise ConflictError("A role with this slug already exists in the workspace")

        sensitive = sorted(p.value for p in (perms & SENSITIVE_PERMISSIONS))
        role = CustomRole(
            workspace_id=workspace_id,
            name=name,
            slug=slug,
            description=description,
            status="pending" if sensitive else "active",
            created_by=actor_id,
            permissions=[CustomRolePermission(permission=p.value) for p in sorted(perms)],
        )
        self.session.add(role)
        await self.session.flush()

        approval: ApprovalRequest | None = None
        if sensitive:
            approval = ApprovalRequest(
                workspace_id=workspace_id,
                kind="custom_role.create",
                subject_id=role.id,
                payload={"role_slug": slug, "sensitive_permissions": sensitive},
                requested_by=actor_id,
            )
            self.session.add(approval)
            await self.session.flush()
            await NotificationService(self.session).notify_workspace_admins(
                workspace_id=workspace_id,
                kind="approval.requested",
                title=f"Approval needed: custom role '{name}'",
                body=f"Requested sensitive permissions: {', '.join(sensitive)}",
                link="/workspace/org",
                exclude_user_id=actor_id,
            )

        self.audit.record(
            actor_id=actor_id,
            action="custom_role.created",
            resource_type="custom_role",
            resource_id=role.id,
            detail={"slug": slug, "status": role.status, "groups": groups},
        )
        await self.session.commit()
        return role, approval

    async def assign(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role_slug: str,
        actor_id: uuid.UUID,
    ) -> WorkspaceMembership:
        role = await self.get_by_slug(workspace_id, role_slug)
        if role is None or role.status != "active":
            # pending/rejected roles are unusable; same message as unknown
            raise NotFoundError("Custom role not found")
        membership = await self.session.get(
            WorkspaceMembership, (workspace_id, user_id)
        )
        if membership is None:
            raise NotFoundError("Membership not found")
        membership.custom_role_id = role.id
        self.audit.record(
            actor_id=actor_id,
            action="custom_role.assigned",
            resource_type="custom_role",
            resource_id=role.id,
            detail={"user_id": str(user_id)},
        )
        await self.session.commit()
        return membership

    async def unassign(
        self, *, workspace_id: uuid.UUID, user_id: uuid.UUID, actor_id: uuid.UUID
    ) -> WorkspaceMembership:
        """Clear a member's custom role, reverting them to their built-in
        workspace role (membership.role, unaffected by this)."""
        membership = await self.session.get(
            WorkspaceMembership, (workspace_id, user_id)
        )
        if membership is None:
            raise NotFoundError("Membership not found")
        previous = membership.custom_role_id
        membership.custom_role_id = None
        if previous is not None:
            self.audit.record(
                actor_id=actor_id,
                action="custom_role.unassigned",
                resource_type="custom_role",
                resource_id=previous,
                detail={"user_id": str(user_id)},
            )
        await self.session.commit()
        return membership


class ApprovalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def list_pending(self, workspace_id: uuid.UUID) -> list[ApprovalRequest]:
        stmt = (
            sa.select(ApprovalRequest)
            .where(
                ApprovalRequest.workspace_id == workspace_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(ApprovalRequest.created_at)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def decide(
        self,
        *,
        approval_id: uuid.UUID,
        workspace_id: uuid.UUID,
        approve: bool,
        reason: str | None,
        actor_id: uuid.UUID,
    ) -> ApprovalRequest:
        approval = await self.session.get(ApprovalRequest, approval_id)
        if (
            approval is None
            or approval.workspace_id != workspace_id
            or approval.status != "pending"
        ):
            raise NotFoundError("Approval request not found")
        if approval.requested_by == actor_id:
            raise ValidationFailure(
                "Approval requires a second admin; you requested this change"
            )

        approval.status = "approved" if approve else "rejected"
        approval.decided_by = actor_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.reason = reason

        if approval.kind == "custom_role.create":
            role = await self.session.get(CustomRole, approval.subject_id)
            if role is not None:
                role.status = "active" if approve else "rejected"

        await NotificationService(self.session).notify(
            user_id=approval.requested_by,
            kind=f"approval.{approval.status}",
            title=f"Your request was {approval.status}",
            body=reason or "",
            workspace_id=workspace_id,
            link="/workspace/org",
        )
        self.audit.record(
            actor_id=actor_id,
            action=f"approval.{approval.status}",
            resource_type="approval_request",
            resource_id=approval.id,
            detail={"kind": approval.kind, "reason": reason},
        )
        await self.session.commit()
        return approval


def effective_custom_permissions(role: CustomRole | None) -> frozenset[Permission]:
    if role is None or role.status != "active":
        return frozenset()
    out: set[Permission] = set()
    for value in role.permission_values:
        try:
            out.add(Permission(value))
        except ValueError:
            continue  # permission retired from the catalog; ignore
    return frozenset(out)
