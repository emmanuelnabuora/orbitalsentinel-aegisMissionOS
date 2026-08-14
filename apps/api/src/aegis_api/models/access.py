"""Programmatic access: invites, API keys (Phase 12).

Security defaults:
- Invite tokens and API key secrets are stored only as SHA-256 hashes.
- Invites are single-use: used_at is set ("burned") before the account
  is created, inside the same transaction.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import Role


class Invite(TimestampMixin, Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(255), index=True)
    role: Mapped[Role] = mapped_column(str_enum(Role))
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )


class ApiKey(TimestampMixin, Base):
    """API key for a service account. Format: aegis_sk_{prefix}_{secret}.

    Only prefix (lookup) and SHA-256 of the full key are stored; the raw
    key is shown exactly once at mint time.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(sa.String(200))
    prefix: Mapped[str] = mapped_column(sa.String(16), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    last_used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
