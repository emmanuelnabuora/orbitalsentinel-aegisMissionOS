"""Identity: users, role assignments, refresh tokens."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    full_name: Mapped[str] = mapped_column(sa.String(200))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    is_service_account: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    clearance: Mapped[str] = mapped_column(sa.String(20), default="unclassified")
    mfa_enabled: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    # TOTP secret, Fernet-encrypted at rest (core/crypto.py)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(sa.String(512))

    role_assignments: Mapped[list["UserRoleAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def roles(self) -> list[Role]:
        return [a.role for a in self.role_assignments]


class UserRoleAssignment(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(str_enum(Role), primary_key=True)

    user: Mapped[User] = relationship(back_populates="role_assignments")


class RefreshToken(Base):
    """Rotating refresh token. Only a SHA-256 hash is stored.

    `family_id` groups a rotation chain: presenting an already-revoked token
    is treated as theft and revokes the entire family.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class MFARecoveryCode(Base):
    """One-time recovery codes; stored as SHA-256 (high-entropy random input)."""

    __tablename__ = "mfa_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
