"""Missions and their asset dependencies."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.asset import Asset
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import Criticality, MissionStatus


class Mission(TimestampMixin, Base):
    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    classification: Mapped[str] = mapped_column(
        sa.String(20), default="unclassified", index=True
    )
    name: Mapped[str] = mapped_column(sa.String(200), index=True)
    description: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[MissionStatus] = mapped_column(
        str_enum(MissionStatus), default=MissionStatus.PLANNING, index=True
    )
    priority: Mapped[Criticality] = mapped_column(str_enum(Criticality), index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )

    asset_links: Mapped[list["MissionAsset"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan", lazy="selectin"
    )


class MissionAsset(Base):
    """Edge: mission depends on asset, with how critically."""

    __tablename__ = "mission_assets"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("missions.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    dependency_criticality: Mapped[Criticality] = mapped_column(
        str_enum(Criticality), default=Criticality.MEDIUM
    )

    mission: Mapped[Mission] = relationship(back_populates="asset_links")
    asset: Mapped[Asset] = relationship(lazy="selectin")
