"""Concrete DB-backed sinks implementing the ingestion ports.

Each operation opens its own session from the factory (the scheduler
runs outside the request lifecycle, so no DI session exists). Idempotency
on dedupe_key is enforced by a pre-check plus the unique index added in
migration b2c4e6a81f00 — the single-scheduler deployment makes the
select-then-insert race window irrelevant, and the index backstops it.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis_api.models.alert import Alert
from aegis_api.models.enums import AlertSeverity
from aegis_api.models.incident import Incident, IncidentEvent
from aegis_api.models.ingestion import AssetEphemeris
from aegis_api.services.ingestion.schemas import AlertDraft, GPRecord


class DbAlertSink:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._factory = session_factory

    async def submit(self, draft: AlertDraft) -> bool:
        async with self._factory() as session:
            exists = (
                await session.execute(
                    sa.select(Alert.id).where(Alert.dedupe_key == draft.dedupe_key)
                )
            ).first()
            if exists:
                return False
            session.add(
                Alert(
                    title=draft.title,
                    description=draft.body,
                    severity=draft.severity,
                    source=draft.source,
                    dedupe_key=draft.dedupe_key,
                )
            )
            await session.commit()
            return True


class DbEphemerisSink:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._factory = session_factory

    async def upsert_many(self, records: list[GPRecord]) -> int:
        async with self._factory() as session:
            for r in records:
                existing = await session.get(AssetEphemeris, r.norad_cat_id)
                if existing is None:
                    existing = AssetEphemeris(norad_cat_id=r.norad_cat_id)
                    session.add(existing)
                existing.object_name = r.object_name
                existing.object_id = r.object_id
                existing.epoch = r.epoch
                existing.mean_motion = r.mean_motion
                existing.eccentricity = r.eccentricity
                existing.inclination = r.inclination
                existing.ra_of_asc_node = r.ra_of_asc_node
                existing.arg_of_pericenter = r.arg_of_pericenter
                existing.mean_anomaly = r.mean_anomaly
                existing.bstar = r.bstar
            await session.commit()
            return len(records)


class DbTrackedAssetLookup:
    """Tracked = present in the asset_ephemeris catalog mirror."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._factory = session_factory

    async def tracked(self, norad_ids: set[int]) -> set[int]:
        if not norad_ids:
            return set()
        async with self._factory() as session:
            rows = await session.execute(
                sa.select(AssetEphemeris.norad_cat_id).where(
                    AssetEphemeris.norad_cat_id.in_(norad_ids)
                )
            )
            return {row[0] for row in rows}


class DbIncidentSink:
    """Opens a system incident from a submitted alert draft.

    Idempotent: keyed through the alert's dedupe_key — if that alert is
    already linked to an incident, this is a no-op. commander_id is NULL
    (system-opened); a SOC manager claims it in the UI.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._factory = session_factory

    async def escalate(self, draft: AlertDraft, reason: str) -> bool:
        async with self._factory() as session:
            alert = (
                await session.execute(
                    sa.select(Alert).where(Alert.dedupe_key == draft.dedupe_key)
                )
            ).scalar_one_or_none()
            if alert is None or alert.incident_id is not None:
                return False
            incident = Incident(
                title=f"[AUTO] {draft.title}",
                summary=f"{reason}. {draft.body}",
                severity=AlertSeverity.CRITICAL,
                commander_id=None,
            )
            session.add(incident)
            await session.flush()
            alert.incident_id = incident.id
            session.add(
                IncidentEvent(
                    incident_id=incident.id,
                    kind="created",
                    message=f"Auto-opened by ingestion: {reason}",
                    actor_id=None,
                )
            )
            session.add(
                IncidentEvent(
                    incident_id=incident.id,
                    kind="alert_linked",
                    message=f"Alert linked: {alert.title}",
                    actor_id=None,
                )
            )
            await session.commit()
            return True
