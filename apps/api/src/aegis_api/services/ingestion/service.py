"""IngestionService — maps raw source data into normalized AlertDrafts.

Severity policy (NOAA G-scale -> platform AlertSeverity):
  Kp >= 7        -> CRITICAL (G3+ strong storm)
  Kp >= 5        -> HIGH     (G1-G2)
  wind >= 800    -> CRITICAL | wind >= 600 -> HIGH
  Bz <= -15 nT   -> CRITICAL | Bz <= -10   -> HIGH (southward IMF)
  SWPC bulletins: WARNING/ALERT -> MEDIUM, WATCH -> LOW, else INFO

Deduplication is by natural key. Kp/wind drafts key on a UTC 3-hour
synoptic bucket so a sustained storm produces one alert per period, not
one per poll. Bulletins key on (product_id, issue_datetime).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from aegis_api.core.logging import get_logger
from aegis_api.models.enums import AlertSeverity
from aegis_api.services.ingestion.clients.base import SourceUnavailable
from aegis_api.services.ingestion.clients.celestrak import CelestrakClient
from aegis_api.services.ingestion.clients.socrates import SocratesClient
from aegis_api.services.ingestion.clients.spacetrack import SpaceTrackClient
from aegis_api.services.ingestion.clients.swpc import SwpcClient
from aegis_api.services.ingestion.schemas import (
    AlertDraft,
    ConjunctionRecord,
    GPRecord,
    KpReading,
    SolarWindSummary,
)

log = get_logger("aegis.ingestion")


class AlertSink(Protocol):
    """Port implemented against the alerts store.

    Must be idempotent on dedupe_key: submitting an existing key is a
    no-op returning False.
    """

    async def submit(self, draft: AlertDraft) -> bool: ...


class TrackedAssetLookup(Protocol):
    """Which of these NORAD ids do we track? (assets/ephemeris join)"""

    async def tracked(self, norad_ids: set[int]) -> set[int]: ...


class IncidentSink(Protocol):
    """Escalation port: open an incident from a submitted alert draft.

    Must be idempotent per dedupe_key (one incident per conjunction).
    """

    async def escalate(self, draft: AlertDraft, reason: str) -> bool: ...


class EphemerisSink(Protocol):
    """Port for GP/ephemeris upserts keyed on norad_cat_id."""

    async def upsert_many(self, records: list[GPRecord]) -> int: ...


def _bucket_3h(ts: datetime) -> str:
    ts = ts.astimezone(timezone.utc)
    return f"{ts:%Y%m%d}T{(ts.hour // 3) * 3:02d}"


def kp_severity(kp: float) -> AlertSeverity | None:
    if kp >= 7:
        return AlertSeverity.CRITICAL
    if kp >= 5:
        return AlertSeverity.HIGH
    return None


def wind_severity(sw: SolarWindSummary) -> AlertSeverity | None:
    sev: AlertSeverity | None = None
    if sw.wind_speed_km_s is not None:
        if sw.wind_speed_km_s >= 800:
            sev = AlertSeverity.CRITICAL
        elif sw.wind_speed_km_s >= 600:
            sev = AlertSeverity.HIGH
    if sw.bz_nt is not None:
        if sw.bz_nt <= -15:
            sev = AlertSeverity.CRITICAL
        elif sw.bz_nt <= -10 and sev is None:
            sev = AlertSeverity.HIGH
    return sev


def conjunction_severity(c: ConjunctionRecord) -> AlertSeverity | None:
    """NASA CARA-style screening thresholds, simplified:
    Pc >= 1e-4 or miss < 1 km  -> CRITICAL (maneuver-consideration territory)
    Pc >= 1e-5 or miss < 5 km  -> HIGH
    Pc >= 1e-7                 -> MEDIUM
    """
    if c.max_probability >= 1e-4 or c.min_range_km < 1.0:
        return AlertSeverity.CRITICAL
    if c.max_probability >= 1e-5 or c.min_range_km < 5.0:
        return AlertSeverity.HIGH
    if c.max_probability >= 1e-7:
        return AlertSeverity.MEDIUM
    return None


def bulletin_severity(message: str) -> AlertSeverity:
    text = message.upper()
    if "WARNING" in text or "ALERT" in text:
        return AlertSeverity.MEDIUM
    if "WATCH" in text:
        return AlertSeverity.LOW
    return AlertSeverity.INFO


class IngestionService:
    def __init__(
        self,
        swpc: SwpcClient,
        celestrak: CelestrakClient,
        alert_sink: AlertSink,
        ephemeris_sink: EphemerisSink | None = None,
        socrates: SocratesClient | None = None,
        spacetrack: SpaceTrackClient | None = None,
        tracked_lookup: TrackedAssetLookup | None = None,
        incident_sink: IncidentSink | None = None,
    ) -> None:
        self._swpc = swpc
        self._celestrak = celestrak
        self._alerts = alert_sink
        self._ephemeris = ephemeris_sink
        self._socrates = socrates
        self._spacetrack = spacetrack
        self._tracked = tracked_lookup
        self._incidents = incident_sink

    # -- space weather ------------------------------------------------------

    async def poll_kp(self) -> AlertDraft | None:
        try:
            reading = await self._swpc.get_latest_kp()
        except SourceUnavailable:
            return None  # fail-open
        if reading is None:
            return None
        return await self._maybe_submit_kp(reading)

    async def _maybe_submit_kp(self, reading: KpReading) -> AlertDraft | None:
        sev = kp_severity(reading.kp_index)
        if sev is None:
            return None
        draft = AlertDraft(
            source="swpc",
            dedupe_key=f"swpc:kp:{_bucket_3h(reading.time_tag)}",
            severity=sev,
            title=f"Geomagnetic storm conditions (Kp {reading.kp_index:.1f})",
            body=(
                f"Estimated planetary Kp reached {reading.kp_index:.1f} at "
                f"{reading.time_tag:%Y-%m-%d %H:%M} UTC. Elevated drag and "
                "charging risk for LEO assets; review QuantumShield posture."
            ),
            observed_at=reading.time_tag,
            metadata={"kp": reading.kp_index},
        )
        await self._alerts.submit(draft)
        return draft

    async def poll_solar_wind(self) -> AlertDraft | None:
        try:
            sw = await self._swpc.get_solar_wind()
        except SourceUnavailable:
            return None
        if sw is None:
            return None
        sev = wind_severity(sw)
        if sev is None:
            return None
        draft = AlertDraft(
            source="swpc",
            dedupe_key=f"swpc:wind:{_bucket_3h(sw.time_tag)}",
            severity=sev,
            title="Elevated solar wind conditions",
            body=(
                f"Solar wind {sw.wind_speed_km_s or 'n/a'} km/s, "
                f"Bt {sw.bt_nt or 'n/a'} nT, Bz {sw.bz_nt or 'n/a'} nT at "
                f"{sw.time_tag:%Y-%m-%d %H:%M} UTC."
            ),
            observed_at=sw.time_tag,
            metadata={
                "wind_speed_km_s": sw.wind_speed_km_s,
                "bt_nt": sw.bt_nt,
                "bz_nt": sw.bz_nt,
            },
        )
        await self._alerts.submit(draft)
        return draft

    async def poll_swpc_bulletins(self) -> int:
        try:
            issued = await self._swpc.get_bulletins()
        except SourceUnavailable:
            return 0
        submitted = 0
        for item in issued:
            first_line = (
                item.message.splitlines()[0][:120] if item.message else item.product_id
            )
            draft = AlertDraft(
                source="swpc",
                dedupe_key=(
                    f"swpc:issued:{item.product_id}:{item.issue_datetime:%Y%m%d%H%M}"
                ),
                severity=bulletin_severity(item.message),
                title=f"SWPC bulletin: {first_line}",
                body=item.message,
                observed_at=item.issue_datetime,
                metadata={"product_id": item.product_id},
            )
            if await self._alerts.submit(draft):
                submitted += 1
        return submitted

    # -- orbital catalog ----------------------------------------------------

    async def refresh_catalog(self, group: str = "active") -> int:
        if self._ephemeris is None:
            return 0
        try:
            records = await self._celestrak.get_group(group)
        except SourceUnavailable:
            return 0
        if not records:
            return 0
        count = await self._ephemeris.upsert_many(records)
        log.info("catalog_refresh", records=count, group=group)
        return count

    # -- conjunctions -------------------------------------------------------

    async def _process_conjunctions(
        self,
        records: list[ConjunctionRecord],
        *,
        source: str,
        dedupe_key_fn,
    ) -> tuple[int, int]:
        """Shared alert-building + escalation logic for any conjunction
        source (SOCRATES, Space-Track CDMs, ...). Only the dedupe-key
        strategy and provenance tag differ per source."""
        involved: set[int] = set()
        for c in records:
            involved.update((c.norad_cat_id_1, c.norad_cat_id_2))
        tracked: set[int] = set()
        if self._tracked is not None and involved:
            tracked = await self._tracked.tracked(involved)

        alerts = incidents = 0
        for c in records:
            sev = conjunction_severity(c)
            if sev is None:
                continue
            involves_tracked = bool({c.norad_cat_id_1, c.norad_cat_id_2} & tracked)
            draft = AlertDraft(
                source=source,
                dedupe_key=dedupe_key_fn(c),
                severity=sev,
                title=(
                    f"Conjunction: {c.object_name_1} × {c.object_name_2} "
                    f"({c.min_range_km:.2f} km)"
                ),
                body=(
                    f"TCA {c.tca:%Y-%m-%d %H:%M} UTC · miss distance "
                    f"{c.min_range_km:.2f} km · relative speed "
                    f"{c.relative_speed_km_s:.2f} km/s · Pc {c.max_probability:.2e}."
                    + (" Involves a tracked asset." if involves_tracked else "")
                ),
                observed_at=c.tca,
                metadata={
                    "norad_1": c.norad_cat_id_1,
                    "norad_2": c.norad_cat_id_2,
                    "min_range_km": c.min_range_km,
                    "max_probability": c.max_probability,
                    "tracked": involves_tracked,
                },
            )
            if await self._alerts.submit(draft):
                alerts += 1
                if (
                    involves_tracked
                    and sev == AlertSeverity.CRITICAL
                    and self._incidents is not None
                ):
                    if await self._incidents.escalate(
                        draft,
                        reason="Critical conjunction involving a tracked asset",
                    ):
                        incidents += 1
        return (alerts, incidents)

    async def poll_conjunctions(self) -> tuple[int, int]:
        """Ingest SOCRATES conjunctions. Returns (alerts, incidents).

        Escalation rule: a CRITICAL conjunction where either object is a
        tracked asset auto-opens an incident linked to the alert.
        """
        if self._socrates is None:
            return (0, 0)
        try:
            records = await self._socrates.get_conjunctions()
        except SourceUnavailable:
            return (0, 0)

        def dedupe_key(c: ConjunctionRecord) -> str:
            # Order-normalized: SOCRATES has no stable per-conjunction id,
            # so the pair + TCA minute stands in for one.
            return (
                f"socrates:{min(c.norad_cat_id_1, c.norad_cat_id_2)}:"
                f"{max(c.norad_cat_id_1, c.norad_cat_id_2)}:{c.tca:%Y%m%d%H%M}"
            )

        alerts, incidents = await self._process_conjunctions(
            records, source="celestrak", dedupe_key_fn=dedupe_key
        )
        if alerts:
            log.info("conjunctions_ingested", alerts=alerts, incidents=incidents)
        return (alerts, incidents)

    async def poll_cdms(self) -> tuple[int, int]:
        """Ingest Space-Track Conjunction Data Messages. Returns
        (alerts, incidents), same shape and escalation rule as
        poll_conjunctions().

        Returns (0, 0) with no error for accounts with no registered
        satellites — Space-Track's CDM class is operator-scoped, not a
        general feed (see clients/spacetrack.py module docstring).
        """
        if self._spacetrack is None:
            return (0, 0)
        try:
            records = await self._spacetrack.get_cdms()
        except SourceUnavailable:
            return (0, 0)

        alerts, incidents = await self._process_conjunctions(
            records,
            source="spacetrack",
            dedupe_key_fn=lambda c: f"spacetrack:cdm:{c.cdm_id}",  # type: ignore[attr-defined]
        )
        if alerts:
            log.info("cdms_ingested", alerts=alerts, incidents=incidents)
        return (alerts, incidents)
