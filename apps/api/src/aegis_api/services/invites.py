"""Invite-based onboarding (Phase 12).

One generic error message for every redemption failure mode — unknown
token, expired, already used, or email conflict — so responses never
enumerate account or invite state.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import ValidationFailure
from aegis_api.core.security import hash_password
from aegis_api.models.access import Invite
from aegis_api.models.enums import Role
from aegis_api.models.user import User, UserRoleAssignment
from aegis_api.models.workspace import WorkspaceMembership
from aegis_api.repositories.users import UserRepository
from aegis_api.services.audit import AuditService
from aegis_api.services.notifications import NotificationService

GENERIC_INVITE_ERROR = "Invalid or expired invitation"
DEFAULT_TTL_HOURS = 72


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InviteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create(
        self,
        *,
        email: str,
        role: Role,
        actor_id: uuid.UUID,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        workspace_id: uuid.UUID | None = None,
    ) -> tuple[Invite, str]:
        """Create an invite; returns (invite, raw_token). Raw token is
        shown exactly once — only its SHA-256 is stored."""
        raw = secrets.token_urlsafe(32)
        invite = Invite(
            email=email.lower(),
            role=role,
            token_hash=_hash(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
            created_by=actor_id,
            workspace_id=workspace_id,
        )
        self.session.add(invite)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="invite.created",
            resource_type="invite",
            resource_id=invite.id,
            detail={"email": invite.email, "role": role.value},
        )
        await self.session.commit()
        return invite, raw

    async def redeem(self, *, token: str, password: str, full_name: str) -> User:
        invite = (
            await self.session.execute(
                sa.select(Invite).where(Invite.token_hash == _hash(token))
            )
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if (
            invite is None
            or invite.used_at is not None
            or invite.expires_at.replace(tzinfo=timezone.utc) < now
            or await UserRepository(self.session).get_by_email(invite.email) is not None
        ):
            raise ValidationFailure(GENERIC_INVITE_ERROR)

        # Burn before account creation, same transaction.
        invite.used_at = now
        user = User(
            email=invite.email,
            password_hash=hash_password(password),
            full_name=full_name,
            # Workspace invites grant a workspace role, not a platform role.
            role_assignments=(
                [] if invite.workspace_id else [UserRoleAssignment(role=invite.role)]
            ),
        )
        self.session.add(user)
        await self.session.flush()
        if invite.workspace_id is not None:
            self.session.add(
                WorkspaceMembership(
                    workspace_id=invite.workspace_id,
                    user_id=user.id,
                    role=invite.role,
                )
            )
        await self.session.flush()
        if invite.created_by is not None:
            await NotificationService(self.session).notify(
                user_id=invite.created_by,
                kind="member.joined",
                title=f"{full_name} accepted your invitation",
                body=invite.email,
                workspace_id=invite.workspace_id,
                link="/workspace/org",
            )
        self.audit.record(
            actor_id=user.id,
            action="invite.redeemed",
            resource_type="user",
            resource_id=user.id,
            detail={"invite_id": str(invite.id)},
        )
        await self.session.commit()
        return user
