"""Authentication: login, rotating refresh tokens with reuse detection, logout.

Refresh tokens are opaque 256-bit secrets; only SHA-256 hashes are stored.
Each login starts a token *family*. Refresh revokes the presented token and
issues a successor in the same family. Presenting an already-revoked token
means the token leaked (client or attacker replayed it) — the entire family
is revoked and the event is audited.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import AuthError
from aegis_api.core.security import (
    TokenError,
    create_access_token,
    decode_mfa_token,
    verify_password,
)
from aegis_api.models.user import RefreshToken, User
from aegis_api.repositories.users import RefreshTokenRepository, UserRepository
from aegis_api.services.audit import AuditService

REFRESH_TTL_DAYS = 14
_GENERIC_FAILURE = "Invalid credentials"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit = AuditService(session)

    async def login(self, email: str, password: str) -> tuple[str | None, str | None, User]:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            self.audit.record(actor_id=None, action="auth.login_failed", detail={"email": email})
            await self.session.commit()
            raise AuthError(_GENERIC_FAILURE)
        if not user.is_active:
            raise AuthError(_GENERIC_FAILURE)

        if user.mfa_enabled:
            # Password verified; second factor pending. No API-capable tokens yet.
            self.audit.record(
                actor_id=user.id,
                action="auth.mfa_challenge",
                resource_type="user",
                resource_id=user.id,
            )
            await self.session.commit()
            return None, None, user

        refresh_plain = self._issue_refresh(user.id, family_id=uuid.uuid4())
        access = create_access_token(str(user.id), roles=[r.value for r in user.roles])
        self.audit.record(
            actor_id=user.id, action="auth.login", resource_type="user", resource_id=user.id
        )
        await self.session.commit()
        return access, refresh_plain, user

    async def complete_mfa_login(self, mfa_token: str, code: str) -> tuple[str, str, User]:
        from aegis_api.services.mfa import MFAService

        try:
            user_id = decode_mfa_token(mfa_token)
        except TokenError as exc:
            raise AuthError("Invalid or expired MFA token") from exc
        user = await self.users.get(uuid.UUID(user_id))
        if user is None or not user.is_active:
            raise AuthError(_GENERIC_FAILURE)
        if not await MFAService(self.session).verify(user, code):
            self.audit.record(
                actor_id=user.id,
                action="auth.mfa_failed",
                resource_type="user",
                resource_id=user.id,
            )
            await self.session.commit()
            raise AuthError("Invalid verification code")

        refresh_plain = self._issue_refresh(user.id, family_id=uuid.uuid4())
        access = create_access_token(str(user.id), roles=[r.value for r in user.roles])
        self.audit.record(
            actor_id=user.id, action="auth.login_mfa", resource_type="user", resource_id=user.id
        )
        await self.session.commit()
        return access, refresh_plain, user

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        record = await self.tokens.get_by_hash(_hash(refresh_token))
        if record is None:
            raise AuthError(_GENERIC_FAILURE)

        if record.revoked_at is not None:
            # Reuse of a rotated token: assume compromise, kill the family.
            await self.tokens.revoke_family(record.family_id)
            self.audit.record(
                actor_id=record.user_id,
                action="auth.refresh_reuse_detected",
                resource_type="token_family",
                resource_id=record.family_id,
            )
            await self.session.commit()
            raise AuthError(_GENERIC_FAILURE)

        now = datetime.now(UTC)
        if _as_utc(record.expires_at) < now:
            raise AuthError(_GENERIC_FAILURE)

        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise AuthError(_GENERIC_FAILURE)

        record.revoked_at = now
        new_plain = self._issue_refresh(user.id, family_id=record.family_id)
        access = create_access_token(str(user.id), roles=[r.value for r in user.roles])
        await self.session.commit()
        return access, new_plain

    async def logout(self, refresh_token: str) -> None:
        record = await self.tokens.get_by_hash(_hash(refresh_token))
        if record is not None:
            await self.tokens.revoke_family(record.family_id)
            self.audit.record(actor_id=record.user_id, action="auth.logout")
            await self.session.commit()
        # Unknown token: succeed silently — logout must be idempotent.

    def _issue_refresh(self, user_id: uuid.UUID, *, family_id: uuid.UUID) -> str:
        plain = secrets.token_urlsafe(32)
        self.tokens.add(
            RefreshToken(
                user_id=user_id,
                token_hash=_hash(plain),
                family_id=family_id,
                expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TTL_DAYS),
            )
        )
        return plain
