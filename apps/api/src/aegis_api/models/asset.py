"""Assets: anything a mission depends on, from satellites to services."""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import AssetStatus, AssetType, Criticality


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(200), index=True)
    description: Mapped[str | None] = mapped_column(sa.Text)
    asset_type: Mapped[AssetType] = mapped_column(str_enum(AssetType), index=True)
    status: Mapped[AssetStatus] = mapped_column(
        str_enum(AssetStatus), default=AssetStatus.UNKNOWN, index=True
    )
    criticality: Mapped[Criticality] = mapped_column(str_enum(Criticality), index=True)
    attributes: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    classification: Mapped[str] = mapped_column(sa.String(20), default="unclassified", index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )


class AssetDependency(Base):
    """Directed edge: `asset_id` depends on `depends_on_id`."""

    __tablename__ = "asset_dependencies"
    __table_args__ = (
        sa.CheckConstraint("asset_id != depends_on_id", name="ck_no_self_dependency"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    criticality: Mapped[Criticality] = mapped_column(
        str_enum(Criticality), default=Criticality.MEDIUM
    )
