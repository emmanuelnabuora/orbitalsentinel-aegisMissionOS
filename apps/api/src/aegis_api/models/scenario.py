"""Saved Digital Twin scenarios: named perturbation sets for replay.

A scenario captures a what-if ("primary ground station loss") so an operator
can re-run it after every fleet change instead of rebuilding it by hand.
Running a scenario never mutates real data — it drives the read-only twin.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin


class Scenario(TimestampMixin, Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(200), index=True)
    description: Mapped[str | None] = mapped_column(sa.Text)
    # Stored perturbation dicts, validated back into Perturbation on run.
    perturbations: Mapped[list] = mapped_column(sa.JSON, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
