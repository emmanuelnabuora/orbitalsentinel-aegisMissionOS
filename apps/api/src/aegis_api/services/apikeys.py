"""Service accounts and API keys (Phase 12).

Service accounts are Users with is_service_account=True and an
unusable password hash (random secret discarded at creation), so they
can never authenticate interactively. Their role is capped at OPERATOR.

Keys: aegis_sk_{prefix}_{secret}. Only the prefix (for lookup) and the
SHA-256 of the full key are stored; the raw key is returned once.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import NotFoundError, ValidationFailure
from aegis_api.core.security import hash_password
from aegis_api.models.access import ApiKey
from aegis_api.models.enums import Role
from aegis_api.models.user import User, UserRoleAssignment
from aegis_api.models.workspace import WorkspaceMembership
from aegis_api.repositories.users import UserRepository
from aegis_api.services.audit import AuditService

KEY_NAMESPACE = "aegis_sk"
SERVICE_ACCOUNT_MAX_ROLE = {Role.OPERATOR, Role.ANALYST, Role.VIEWER}


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ServiceAccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        *,
        name: str,
        email: str,
        role: Role,
        actor_id: uuid.UUID,
        workspace_id: uuid.UUID | None = None,
    ) -> User:
        if role not in SERVICE_ACCOUNT_MAX_ROLE:
            raise ValidationFailure("Service accounts are capped at the operator role")
        if await self.repo.get_by_email(email) is not None:
            raise ValidationFailure("Unable to create service account")
        account = User(
            email=email.lower(),
            # Unusable: random secret hashed then discarded.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=name,
            is_service_account=True,
            role_assignments=([] if workspace_id else [UserRoleAssignment(role=role)]),
        )
        self.session.add(account)
        await self.session.flush()
        if workspace_id is not None:
            self.session.add(
                WorkspaceMembership(workspace_id=workspace_id, user_id=account.id, role=role)
            )
        self.audit.record(
            actor_id=actor_id,
            action="service_account.created",
            resource_type="user",
            resource_id=account.id,
            detail={"role": role.value},
        )
        await self.session.commit()
        return account

    async def list_for_workspace(self, workspace_id: uuid.UUID) -> list[tuple[User, list[ApiKey]]]:
        """Service accounts that are members of this workspace, each paired with its keys.

        No ORM relationship exists between User and ApiKey (keys are looked
        up by prefix at auth time, never traversed from the user side), so
        this does the account query and the keys query separately rather
        than forcing a relationship that only this listing needs.
        """
        accounts_stmt = (
            sa.select(User)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                User.is_service_account.is_(True),
            )
            .order_by(User.created_at)
        )
        accounts = list((await self.session.execute(accounts_stmt)).scalars())
        if not accounts:
            return []
        account_ids = [a.id for a in accounts]
        keys_stmt = (
            sa.select(ApiKey).where(ApiKey.user_id.in_(account_ids)).order_by(ApiKey.created_at)
        )
        keys = list((await self.session.execute(keys_stmt)).scalars())
        keys_by_account: dict[uuid.UUID, list[ApiKey]] = {aid: [] for aid in account_ids}
        for k in keys:
            keys_by_account[k.user_id].append(k)
        return [(a, keys_by_account[a.id]) for a in accounts]


class ApiKeyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def mint(
        self, *, account_id: uuid.UUID, name: str, actor_id: uuid.UUID
    ) -> tuple[ApiKey, str]:
        account = await UserRepository(self.session).get(account_id)
        if account is None or not account.is_service_account:
            raise NotFoundError("Service account not found")
        prefix = secrets.token_hex(4)  # 8 chars
        secret = secrets.token_urlsafe(32)
        raw = f"{KEY_NAMESPACE}_{prefix}_{secret}"
        key = ApiKey(user_id=account.id, name=name, prefix=prefix, key_hash=_hash(raw))
        self.session.add(key)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="api_key.minted",
            resource_type="api_key",
            resource_id=key.id,
            detail={"account_id": str(account.id), "prefix": prefix},
        )
        await self.session.commit()
        return key, raw

    async def revoke(self, *, key_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        key = await self.session.get(ApiKey, key_id)
        if key is None or key.revoked_at is not None:
            raise NotFoundError("API key not found")
        key.revoked_at = datetime.now(UTC)
        self.audit.record(
            actor_id=actor_id,
            action="api_key.revoked",
            resource_type="api_key",
            resource_id=key.id,
            detail={"prefix": key.prefix},
        )
        await self.session.commit()

    async def authenticate(self, raw_key: str) -> User | None:
        """Resolve an X-API-Key value to an active service account, or None.

        Constant-shape flow: prefix lookup, hash compare, activity checks.
        Any failure mode returns None (no enumeration).
        """
        # Secret is token_urlsafe and may itself contain underscores.
        parts = raw_key.split("_", 3)
        if len(parts) != 4 or f"{parts[0]}_{parts[1]}" != KEY_NAMESPACE:
            return None
        prefix = parts[2]
        key = (
            await self.session.execute(sa.select(ApiKey).where(ApiKey.prefix == prefix))
        ).scalar_one_or_none()
        if (
            key is None
            or key.revoked_at is not None
            or not secrets.compare_digest(key.key_hash, _hash(raw_key))
        ):
            return None
        account = await UserRepository(self.session).get(key.user_id)
        if account is None or not account.is_active or not account.is_service_account:
            return None
        key.last_used_at = datetime.now(UTC)
        await self.session.commit()
        return account
