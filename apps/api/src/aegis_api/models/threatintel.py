"""Threat intelligence: indicators of compromise and correlation matches."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.asset import Asset
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import AlertSeverity, IndicatorType, ThreatCategory


class ThreatIndicator(TimestampMixin, Base):
    __tablename__ = "threat_indicators"
    __table_args__ = (
        # An IOC is identified by (type, value); feeds update, never duplicate.
        sa.UniqueConstraint("indicator_type", "value", name="uq_indicator_type_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    indicator_type: Mapped[IndicatorType] = mapped_column(str_enum(IndicatorType), index=True)
    value: Mapped[str] = mapped_column(sa.String(500), index=True)
    category: Mapped[ThreatCategory] = mapped_column(
        str_enum(ThreatCategory), default=ThreatCategory.UNKNOWN, index=True
    )
    severity: Mapped[AlertSeverity] = mapped_column(str_enum(AlertSeverity), index=True)
    confidence: Mapped[int] = mapped_column(sa.Integer, default=50)  # 0-100
    source: Mapped[str] = mapped_column(sa.String(100), index=True)
    description: Mapped[str | None] = mapped_column(sa.Text)
    active: Mapped[bool] = mapped_column(sa.Boolean, default=True, index=True)
    first_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class ThreatMatch(Base):
    """An indicator observed on one of our assets. Raising these creates alerts."""

    __tablename__ = "threat_matches"
    __table_args__ = (
        sa.UniqueConstraint("indicator_id", "asset_id", name="uq_match_indicator_asset"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    indicator_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("threat_indicators.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("alerts.id", ondelete="SET NULL")
    )
    matched_on: Mapped[str] = mapped_column(sa.String(200))  # which attribute matched
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    indicator: Mapped[ThreatIndicator] = relationship(lazy="selectin")
    asset: Mapped[Asset] = relationship(lazy="selectin")
