"""Seed a demo environment: admin user, sample assets, one mission with a
dependency graph. Idempotent — safe to run repeatedly.

Usage:
    AEGIS_ADMIN_EMAIL=admin@example.com AEGIS_ADMIN_PASSWORD='...' \
        python scripts/seed.py
"""

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker

from aegis_api.core.db import get_engine
from aegis_api.models.enums import (
    AlertSeverity,
    AssetStatus,
    AssetType,
    Criticality,
    CryptoKind,
    MissionStatus,
    Role,
)
from aegis_api.repositories.assets import AssetRepository
from aegis_api.repositories.users import UserRepository
from aegis_api.schemas.alert import AlertCreate
from aegis_api.schemas.asset import AssetCreate, AssetDependencyCreate
from aegis_api.schemas.incident import IncidentCreate
from aegis_api.schemas.mission import MissionAssetAttach, MissionCreate
from aegis_api.schemas.quantum import CryptoRecordCreate
from aegis_api.services.alerts import AlertService
from aegis_api.services.assets import AssetService
from aegis_api.services.incidents import IncidentService
from aegis_api.services.missions import MissionService
from aegis_api.services.quantum import QuantumService
from aegis_api.services.users import UserService

ASSETS = [
    AssetCreate(
        name="SENTRY-7",
        asset_type=AssetType.SATELLITE,
        criticality=Criticality.CRITICAL,
        status=AssetStatus.OPERATIONAL,
        description="LEO comms satellite, northern corridor",
        attributes={"orbit": "LEO", "norad_id": "99901", "lat": 51.2, "lon": -42.5},
    ),
    AssetCreate(
        name="Vandenberg Ground Station",
        asset_type=AssetType.GROUND_STATION,
        criticality=Criticality.HIGH,
        status=AssetStatus.OPERATIONAL,
        attributes={"band": "S/X", "antennas": 3, "lat": 34.74, "lon": -120.57},
    ),
    AssetCreate(
        name="Telemetry Ingest Service",
        asset_type=AssetType.APPLICATION,
        criticality=Criticality.HIGH,
        status=AssetStatus.OPERATIONAL,
    ),
]


async def main() -> None:
    email = os.environ.get("AEGIS_ADMIN_EMAIL")
    password = os.environ.get("AEGIS_ADMIN_PASSWORD")
    if not email or not password:
        sys.exit("Set AEGIS_ADMIN_EMAIL and AEGIS_ADMIN_PASSWORD (min 12 chars).")
    if len(password) < 12:
        sys.exit("AEGIS_ADMIN_PASSWORD must be at least 12 characters.")

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        users = UserRepository(session)
        admin = await users.get_by_email(email)
        if admin is None:
            admin = await UserService(session).create(
                email=email,
                password=password,
                full_name="Platform Admin",
                roles=[Role.ADMIN, Role.OPERATOR],
                actor_id=None,
            )
            print(f"created admin {email}")
        else:
            print(f"admin {email} already exists")

        assets_svc = AssetService(session)
        asset_repo = AssetRepository(session)
        created = {}
        for spec in ASSETS:
            existing, _ = await asset_repo.list(limit=1, offset=0, search=spec.name)
            if existing:
                created[spec.name] = existing[0]
                continue
            created[spec.name] = await assets_svc.create(spec, actor_id=admin.id)
            print(f"created asset {spec.name}")

        missions_svc = MissionService(session)
        existing, _ = await missions_svc.repo.list(limit=50, offset=0)
        if not any(m.name == "OVERWATCH-ALPHA" for m in existing):
            mission = await missions_svc.create(
                MissionCreate(
                    name="OVERWATCH-ALPHA",
                    priority=Criticality.CRITICAL,
                    status=MissionStatus.ACTIVE,
                    description="Persistent comms coverage, northern corridor",
                ),
                actor_id=admin.id,
            )
            for name, crit in [
                ("SENTRY-7", Criticality.CRITICAL),
                ("Vandenberg Ground Station", Criticality.HIGH),
                ("Telemetry Ingest Service", Criticality.HIGH),
            ]:
                await missions_svc.attach_asset(
                    mission.id,
                    MissionAssetAttach(asset_id=created[name].id, dependency_criticality=crit),
                    actor_id=admin.id,
                )
            await assets_svc.add_dependency(
                created["SENTRY-7"].id,
                AssetDependencyCreate(
                    depends_on_id=created["Vandenberg Ground Station"].id,
                    criticality=Criticality.CRITICAL,
                ),
                actor_id=admin.id,
            )
            print("created mission OVERWATCH-ALPHA with dependency graph")

            alerts_svc = AlertService(session)
            a1 = await alerts_svc.create(
                AlertCreate(
                    title="Telemetry signal anomaly on SENTRY-7 downlink",
                    description="Downlink SNR dropped 40% over 12 minutes.",
                    severity=AlertSeverity.HIGH,
                    source="SpaceShield",
                    asset_id=created["SENTRY-7"].id,
                ),
                actor_id=admin.id,
            )
            await alerts_svc.create(
                AlertCreate(
                    title="Repeated auth failures at ground station gateway",
                    severity=AlertSeverity.MEDIUM,
                    source="GroundShield",
                    asset_id=created["Vandenberg Ground Station"].id,
                ),
                actor_id=admin.id,
            )
            await IncidentService(session).create(
                IncidentCreate(
                    title="Downlink instability - northern corridor",
                    summary="Investigating RF anomaly affecting mission comms.",
                    severity=AlertSeverity.HIGH,
                    alert_ids=[a1.id],
                ),
                actor_id=admin.id,
            )

            q = QuantumService(session)
            for rec in [
                CryptoRecordCreate(
                    asset_id=created["Vandenberg Ground Station"].id,
                    kind=CryptoKind.CERTIFICATE,
                    algorithm="RSA",
                    key_size=2048,
                    subject="CN=vandenberg.gs.mil",
                ),
                CryptoRecordCreate(
                    asset_id=created["Telemetry Ingest Service"].id,
                    kind=CryptoKind.TLS_ENDPOINT,
                    algorithm="ECDSA",
                    key_size=256,
                ),
                CryptoRecordCreate(
                    asset_id=created["SENTRY-7"].id,
                    kind=CryptoKind.DATA_AT_REST,
                    algorithm="AES-256-GCM",
                ),
                CryptoRecordCreate(
                    asset_id=created["SENTRY-7"].id,
                    kind=CryptoKind.TLS_ENDPOINT,
                    algorithm="ML-KEM",
                ),
            ]:
                await q.register(rec, actor_id=admin.id)
            print("seeded alerts, incident, crypto inventory")

            from aegis_api.services.threatintel.engine import ThreatIntelService

            # A network asset carrying a known-bad management IP so a fresh
            # ingest+correlate produces a visible ThreatIntel alert in the demo.
            await AssetService(session).create(
                AssetCreate(
                    name="Northern Corridor Relay",
                    asset_type=AssetType.NETWORK,
                    criticality=Criticality.HIGH,
                    status=AssetStatus.OPERATIONAL,
                    attributes={"mgmt_ip": "203.0.113.66", "site": "GS-NORTH"},
                ),
                actor_id=admin.id,
            )
            ti_svc = ThreatIntelService(session)
            await ti_svc.ingest(actor_id=admin.id)
            correlation = await ti_svc.correlate(actor_id=admin.id)
            print(
                f"seeded threat intel: ingested curated feed, "
                f"{correlation.alerts_raised} alert(s) raised via correlation"
            )

    print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())
