"""TOTP multi-factor authentication with one-time recovery codes."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

import pyotp
import qrcode
import qrcode.image.svg
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core import crypto
from aegis_api.core.exceptions import AuthError, ConflictError
from aegis_api.models.user import MFARecoveryCode, User
from aegis_api.services.audit import AuditService

RECOVERY_CODE_COUNT = 10


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class MFAService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    def _provisioning(self, user: User, secret: str) -> tuple[str, str]:
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="AEGIS MissionOS")
        img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
        return uri, img.to_string(encoding="unicode")

    async def start_setup(self, user: User) -> tuple[str, str, str]:
        """Generate and store a pending TOTP secret; returns (secret, uri, qr_svg)."""
        if user.mfa_enabled:
            raise ConflictError("MFA is already enabled")
        secret = pyotp.random_base32()
        user.mfa_secret_encrypted = crypto.encrypt(secret)
        await self.session.commit()
        uri, svg = self._provisioning(user, secret)
        return secret, uri, svg

    async def activate(self, user: User, code: str) -> list[str]:
        """Verify first code, enable MFA, return one-time recovery codes."""
        if user.mfa_enabled:
            raise ConflictError("MFA is already enabled")
        if not user.mfa_secret_encrypted:
            raise AuthError("MFA setup has not been started")
        secret = crypto.decrypt(user.mfa_secret_encrypted)
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise AuthError("Invalid verification code")

        user.mfa_enabled = True
        codes = [secrets.token_hex(5) for _ in range(RECOVERY_CODE_COUNT)]
        for c in codes:
            self.session.add(MFARecoveryCode(user_id=user.id, code_hash=_hash_code(c)))
        self.audit.record(
            actor_id=user.id, action="mfa.enabled", resource_type="user", resource_id=user.id
        )
        await self.session.commit()
        return codes

    async def verify(self, user: User, code: str) -> bool:
        """Accept a current TOTP code or an unused recovery code (consumed)."""
        if not (user.mfa_enabled and user.mfa_secret_encrypted):
            raise AuthError("MFA is not enabled")
        secret = crypto.decrypt(user.mfa_secret_encrypted)
        if pyotp.TOTP(secret).verify(code, valid_window=1):
            return True
        row = (
            await self.session.execute(
                sa.select(MFARecoveryCode).where(
                    MFARecoveryCode.user_id == user.id,
                    MFARecoveryCode.code_hash == _hash_code(code),
                    MFARecoveryCode.used_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        row.used_at = datetime.now(UTC)
        self.audit.record(
            actor_id=user.id,
            action="mfa.recovery_code_used",
            resource_type="user",
            resource_id=user.id,
        )
        await self.session.commit()
        return True

    async def disable(self, user: User, code: str) -> None:
        """Disabling proves possession of a current factor."""
        if not await self.verify(user, code):
            raise AuthError("Invalid verification code")
        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        await self.session.execute(
            sa.delete(MFARecoveryCode).where(MFARecoveryCode.user_id == user.id)
        )
        self.audit.record(
            actor_id=user.id, action="mfa.disabled", resource_type="user", resource_id=user.id
        )
        await self.session.commit()

    async def unused_recovery_count(self, user_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                sa.select(sa.func.count(MFARecoveryCode.id)).where(
                    MFARecoveryCode.user_id == user_id,
                    MFARecoveryCode.used_at.is_(None),
                )
            )
        ).scalar_one()
