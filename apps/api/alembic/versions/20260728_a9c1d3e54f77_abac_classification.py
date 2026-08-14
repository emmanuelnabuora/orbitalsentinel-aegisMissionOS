"""abac: user clearance and resource classification markings

Revision ID: a9c1d3e54f77
Revises: f4a6b8d93e11
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op

revision = 'a9c1d3e54f77'
down_revision = 'f4a6b8d93e11'
branch_labels = None
depends_on = None

_TABLES = ("assets", "missions", "alerts", "incidents")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("clearance", sa.String(20), nullable=False, server_default="unclassified"),
    )
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("classification", sa.String(20), nullable=False, server_default="unclassified"),
        )
        op.create_index(f"ix_{table}_classification", table, ["classification"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_classification", table_name=table)
        op.drop_column(table, "classification")
    op.drop_column("users", "clearance")
