"""Shared model building blocks."""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column


def str_enum(enum_cls: type[StrEnum]) -> sa.Enum:
    """String-backed enum column: CHECK constraint, no native pg enum.

    Portable across Postgres and SQLite, and adding a member is an
    ALTER-free migration.
    """
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=30,
        values_callable=lambda e: [m.value for m in e],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
