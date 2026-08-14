"""Incidents: investigations grouping alerts, with an append-only timeline."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import AlertSeverity, IncidentStatus


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    classification: Mapped[str] = mapped_column(
        sa.String(20), default="unclassified", index=True
    )
    title: Mapped[str] = mapped_column(sa.String(300))
    summary: Mapped[str | None] = mapped_column(sa.Text)
    severity: Mapped[AlertSeverity] = mapped_column(str_enum(AlertSeverity), index=True)
    status: Mapped[IncidentStatus] = mapped_column(
        str_enum(IncidentStatus), default=IncidentStatus.OPEN, index=True
    )
    commander_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )

    events: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="IncidentEvent.at",
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    kind: Mapped[str] = mapped_column(sa.String(50))  # created|status|note|alert_linked|ai_analysis
    message: Mapped[str] = mapped_column(sa.Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )

    incident: Mapped[Incident] = relationship(back_populates="events")
