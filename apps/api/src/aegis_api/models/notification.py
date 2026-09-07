"""In-app notifications and per-user workspace preferences (Phase 15)."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(
        sa.String(50), index=True
    )  # approval.requested, alert.critical, member.joined, ...
    title: Mapped[str] = mapped_column(sa.String(200))
    body: Mapped[str] = mapped_column(sa.String(1000), default="")
    link: Mapped[str | None] = mapped_column(sa.String(200))  # in-app route
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), index=True)


class WorkspacePreference(TimestampMixin, Base):
    """Per-user, per-workspace UI preferences: default workspace flag,
    muted notification kinds, dashboard layout — one JSON document."""

    __tablename__ = "workspace_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(sa.JSON, default=dict)
