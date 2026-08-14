"""DB-backed custom roles and approval workflows (Phase 14).

Custom roles are workspace-scoped bundles of permissions composed from
code-defined permission groups. Roles that include sensitive
permissions activate only after a second workspace admin approves.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin


class CustomRole(TimestampMixin, Base):
    __tablename__ = "custom_roles"
    __table_args__ = (sa.UniqueConstraint("workspace_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(sa.String(100))
    slug: Mapped[str] = mapped_column(sa.String(80))
    description: Mapped[str | None] = mapped_column(sa.String(500))
    status: Mapped[str] = mapped_column(sa.String(20), default="active")  # active|pending|rejected
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )

    permissions: Mapped[list["CustomRolePermission"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def permission_values(self) -> list[str]:
        return [p.permission for p in self.permissions]


class CustomRolePermission(Base):
    __tablename__ = "custom_role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("custom_roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission: Mapped[str] = mapped_column(sa.String(60), primary_key=True)


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(sa.String(50))  # e.g. custom_role.create
    subject_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)  # e.g. custom_roles.id
    payload: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    status: Mapped[str] = mapped_column(sa.String(20), default="pending")  # pending|approved|rejected
    requested_by: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE")
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(sa.String(500))
