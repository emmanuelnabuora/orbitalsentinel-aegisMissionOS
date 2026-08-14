"""custom roles, permission storage, approval workflows

Revision ID: e1f3a5c72d88
Revises: c7d9f2b41a55
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op

revision = 'e1f3a5c72d88'
down_revision = 'c7d9f2b41a55'
branch_labels = None
depends_on = None




def upgrade() -> None:
    op.create_table(
        "custom_roles",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.UniqueConstraint("workspace_id", "slug"),
    )
    op.create_index("ix_custom_roles_workspace_id", "custom_roles", ["workspace_id"])

    op.create_table(
        "custom_role_permissions",
        sa.Column("role_id", sa.Uuid, sa.ForeignKey("custom_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(60), primary_key=True),
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("subject_id", sa.Uuid, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decided_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )
    op.create_index("ix_approval_requests_workspace_id", "approval_requests", ["workspace_id"])

    op.add_column(
        "workspace_members",
        sa.Column("custom_role_id", sa.Uuid, sa.ForeignKey("custom_roles.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspace_members", "custom_role_id")
    op.drop_index("ix_approval_requests_workspace_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_table("custom_role_permissions")
    op.drop_index("ix_custom_roles_workspace_id", table_name="custom_roles")
    op.drop_table("custom_roles")
