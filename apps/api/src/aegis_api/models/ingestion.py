"""Asset ephemeris: latest GP/OMM orbital elements per NORAD object.

Standalone table keyed on norad_cat_id (expand-then-contract: assets may
later gain a norad linkage without touching this write path).
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin


class AssetEphemeris(TimestampMixin, Base):
    __tablename__ = "asset_ephemeris"

    norad_cat_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    object_name: Mapped[str] = mapped_column(sa.String(200), index=True)
    object_id: Mapped[str] = mapped_column(sa.String(50))  # intl designator
    epoch: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    mean_motion: Mapped[float] = mapped_column(sa.Float)  # rev/day
    eccentricity: Mapped[float] = mapped_column(sa.Float)
    inclination: Mapped[float] = mapped_column(sa.Float)  # deg
    ra_of_asc_node: Mapped[float] = mapped_column(sa.Float)
    arg_of_pericenter: Mapped[float] = mapped_column(sa.Float)
    mean_anomaly: Mapped[float] = mapped_column(sa.Float)
    bstar: Mapped[float] = mapped_column(sa.Float, default=0.0)
