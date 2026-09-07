"""Alerts: signals requiring attention, optionally tied to assets/incidents."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.asset import Asset
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import AlertSeverity, AlertStatus


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(sa.String(300))
    description: Mapped[str | None] = mapped_column(sa.Text)
    severity: Mapped[AlertSeverity] = mapped_column(str_enum(AlertSeverity), index=True)
    status: Mapped[AlertStatus] = mapped_column(
        str_enum(AlertStatus), default=AlertStatus.OPEN, index=True
    )
    source: Mapped[str] = mapped_column(sa.String(100), default="manual")
    classification: Mapped[str] = mapped_column(sa.String(20), default="unclassified", index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    dedupe_key: Mapped[str | None] = mapped_column(
        sa.String(200), unique=True, index=True
    )  # natural key for idempotent ingestion (Phase 11)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("assets.id", ondelete="SET NULL"), index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("incidents.id", ondelete="SET NULL"), index=True
    )

    asset: Mapped[Asset | None] = relationship(lazy="selectin")
