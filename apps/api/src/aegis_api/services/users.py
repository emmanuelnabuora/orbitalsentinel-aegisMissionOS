from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import ConflictError, NotFoundError, ValidationFailure
from aegis_api.core.security import hash_password
from aegis_api.models.enums import Role
from aegis_api.models.user import User, UserRoleAssignment
from aegis_api.repositories.users import UserRepository
from aegis_api.services.audit import AuditService


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        roles: list[Role],
        actor_id: uuid.UUID | None,
    ) -> User:
        if await self.repo.get_by_email(email) is not None:
            raise ConflictError("A user with this email already exists")
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            role_assignments=[UserRoleAssignment(role=r) for r in set(roles)],
        )
        self.repo.add(user)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="user.created",
            resource_type="user",
            resource_id=user.id,
            detail={"roles": [r.value for r in roles]},
        )
        await self.session.commit()
        return user

    async def list(self, *, limit: int, offset: int) -> tuple[list[User], int]:
        return await self.repo.list(limit=limit, offset=offset)

    async def _admin_count(self) -> int:
        stmt = sa.select(sa.func.count(sa.func.distinct(UserRoleAssignment.user_id))).where(
            UserRoleAssignment.role == Role.ADMIN
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def set_roles(
        self, *, user_id: uuid.UUID, roles: list[Role], actor_id: uuid.UUID
    ) -> User:
        """Wholesale-replace a user's platform roles.

        Guards mirror the workspace-admin lockout (ADR-0012): the sole
        remaining platform admin cannot demote themself, and the last
        platform admin cannot be stripped of the role by anyone.
        """
        target = await self.repo.get(user_id)
        if target is None:
            raise NotFoundError("User not found")

        was_admin = Role.ADMIN in set(target.roles)
        will_be_admin = Role.ADMIN in set(roles)
        if was_admin and not will_be_admin:
            if await self._admin_count() <= 1:
                msg = (
                    "You cannot remove your own admin role — you are the last platform admin"
                    if user_id == actor_id
                    else "Cannot remove the last platform admin's admin role"
                )
                raise ValidationFailure(msg)

        target.role_assignments = [UserRoleAssignment(role=r) for r in set(roles)]
        self.audit.record(
            actor_id=actor_id,
            action="user.roles_changed",
            resource_type="user",
            resource_id=target.id,
            detail={"roles": sorted(r.value for r in set(roles))},
        )
        await self.session.commit()
        await self.session.refresh(target)
        return target
