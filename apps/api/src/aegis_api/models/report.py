"""Reports: versioned, immutable snapshots of platform state at generation time.

A report's `content` is a structured JSON document (sections with headings and
prose/tables) produced by the reporting engine from live data. Snapshots are
immutable: regenerating creates a new row, so a report cited in a review always
renders exactly as it did when issued.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from aegis_api.core.db import Base
from aegis_api.models.common import str_enum
from aegis_api.models.enums import ReportKind


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[ReportKind] = mapped_column(str_enum(ReportKind), index=True)
    title: Mapped[str] = mapped_column(sa.String(300))
    # Optional subject (e.g. the incident a report is about)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, index=True)
    # Structured document: {"summary": str, "sections": [{"heading", "body", "rows"?}]}
    content: Mapped[dict] = mapped_column(sa.JSON)
    # Provenance: which SentinelAI provider generated the narrative
    provider: Mapped[str] = mapped_column(sa.String(100), default="sentinel-rules-v1")
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True
    )
