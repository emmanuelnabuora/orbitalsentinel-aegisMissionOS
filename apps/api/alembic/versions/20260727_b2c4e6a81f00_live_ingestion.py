"""live ingestion: alerts.dedupe_key + asset_ephemeris

Revision ID: b2c4e6a81f00
Revises: 537d4ef8dd44
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op

revision = 'b2c4e6a81f00'
down_revision = '537d4ef8dd44'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand-then-contract (ADR-0005): nullable column, no backfill needed —
    # only ingestion-created alerts carry a dedupe key.
    op.add_column("alerts", sa.Column("dedupe_key", sa.String(200), nullable=True))
    op.create_index("ix_alerts_dedupe_key", "alerts", ["dedupe_key"], unique=True)

    op.create_table(
        "asset_ephemeris",
        sa.Column("norad_cat_id", sa.Integer, primary_key=True),
        sa.Column("object_name", sa.String(200), nullable=False),
        sa.Column("object_id", sa.String(50), nullable=False),
        sa.Column("epoch", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mean_motion", sa.Float, nullable=False),
        sa.Column("eccentricity", sa.Float, nullable=False),
        sa.Column("inclination", sa.Float, nullable=False),
        sa.Column("ra_of_asc_node", sa.Float, nullable=False),
        sa.Column("arg_of_pericenter", sa.Float, nullable=False),
        sa.Column("mean_anomaly", sa.Float, nullable=False),
        sa.Column("bstar", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )
    op.create_index("ix_asset_ephemeris_object_name", "asset_ephemeris", ["object_name"])


def downgrade() -> None:
    op.drop_index("ix_asset_ephemeris_object_name", table_name="asset_ephemeris")
    op.drop_table("asset_ephemeris")
    op.drop_index("ix_alerts_dedupe_key", table_name="alerts")
    op.drop_column("alerts", "dedupe_key")
