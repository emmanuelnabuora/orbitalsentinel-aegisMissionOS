"""Workspaces: the multi-tenancy boundary (Phase 12).

A workspace groups users (via memberships, each carrying a
workspace-scoped role) and owns domain resources. Resource scoping is
expand-then-contract (ADR-0005): workspace_id columns are nullable, so
pre-existing single-tenant data keeps working while new writes scope.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_api.core.db import Base
from aegis_api.models.common import TimestampMixin, str_enum
from aegis_api.models.enums import Role


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(200))
    slug: Mapped[str] = mapped_column(sa.String(80), unique=True, index=True)

    members: Mapped[list["WorkspaceMembership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkspaceMembership(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(str_enum(Role))
    # When set, the custom role's permission set REPLACES the built-in
    # role's for workspace-scoped authorization (Phase 14).
    custom_role_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("custom_roles.id", ondelete="SET NULL")
    )

    workspace: Mapped[Workspace] = relationship(back_populates="members")
