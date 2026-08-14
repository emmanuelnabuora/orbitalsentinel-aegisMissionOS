"""Phase 11 — live data ingestion.

All network is mocked via httpx.MockTransport; DB tests run against the
standard hermetic db fixture (SQLite in-memory / Postgres in CI).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from aegis_api.models.alert import Alert
from aegis_api.models.enums import AlertSeverity
from aegis_api.models.ingestion import AssetEphemeris
from aegis_api.services.ingestion.clients.base import BaseSourceClient, SourceUnavailable
from aegis_api.services.ingestion.clients.celestrak import CelestrakClient
from aegis_api.services.ingestion.clients.swpc import SwpcClient
from aegis_api.services.ingestion.schemas import SolarWindSummary
from aegis_api.services.ingestion.service import (
    IngestionService,
    bulletin_severity,
    kp_severity,
    wind_severity,
)
from aegis_api.services.ingestion.sinks import DbAlertSink, DbEphemerisSink

NOW = datetime(2026, 7, 18, 3, 5, tzinfo=timezone.utc)

CELESTRAK_GP_JSON = [
    {
        "OBJECT_NAME": "ISS (ZARYA)",
        "OBJECT_ID": "1998-067A",
        "NORAD_CAT_ID": 25544,
        "EPOCH": "2026-07-17T12:00:00",
        "MEAN_MOTION": 15.50129011,
        "ECCENTRICITY": 0.0006703,
        "INCLINATION": 51.6416,
        "RA_OF_ASC_NODE": 247.4627,
        "ARG_OF_PERICENTER": 130.536,
        "MEAN_ANOMALY": 325.0288,
        "BSTAR": 0.000028,
    },
    {
        "OBJECT_NAME": "SENTINEL-DEMO 1",
        "OBJECT_ID": "2025-101A",
        "NORAD_CAT_ID": 61001,
        "EPOCH": "2026-07-17T10:30:00",
        "MEAN_MOTION": 14.2,
        "ECCENTRICITY": 0.001,
        "INCLINATION": 97.5,
        "RA_OF_ASC_NODE": 10.0,
        "ARG_OF_PERICENTER": 90.0,
        "MEAN_ANOMALY": 270.0,
        "BSTAR": 0.0001,
    },
]

KP_STORM_JSON = [
    {"time_tag": "2026-07-18 00:00:00.000", "kp_index": 4, "estimated_kp": 4.33},
    {"time_tag": "2026-07-18 03:00:00.000", "kp_index": 6, "estimated_kp": 6.67},
]
KP_QUIET_JSON = [
    {"time_tag": "2026-07-18 03:00:00.000", "kp_index": 2, "estimated_kp": 2.0},
]
WIND_SPEED_JSON = {"WindSpeed": "812.3", "TimeStamp": "2026-07-18 03:05:00"}
WIND_MAG_JSON = {"Bt": "22.1", "Bz": "-18.4", "TimeStamp": "2026-07-18 03:05:00"}
SWPC_BULLETINS_JSON = [
    {
        "product_id": "K06W",
        "issue_datetime": "2026-07-18 02:41:00.000",
        "message": "WARNING: Geomagnetic K-index of 6 expected\nValid to 2026 Jul 18 0600 UTC",
    },
    {
        "product_id": "A20F",
        "issue_datetime": "2026-07-18 01:10:00.000",
        "message": "WATCH: Geomagnetic storm category G2 predicted",
    },
]


def make_swpc_client(*, storm: bool = True, fail: bool = False) -> SwpcClient:
    kp = KP_STORM_JSON if storm else KP_QUIET_JSON

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503, text="unavailable")
        path = request.url.path
        if path.endswith("planetary_k_index_1m.json"):
            return httpx.Response(200, json=kp)
        if path.endswith("solar-wind-speed.json"):
            return httpx.Response(200, json=WIND_SPEED_JSON)
        if path.endswith("solar-wind-mag-field.json"):
            return httpx.Response(200, json=WIND_MAG_JSON)
        if path.endswith("alerts.json"):
            return httpx.Response(200, json=SWPC_BULLETINS_JSON)
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://services.swpc.noaa.gov",
        transport=httpx.MockTransport(handler),
    )
    return SwpcClient(client=client, max_retries=2, backoff_base_s=0.0)


def make_celestrak_client(*, empty: bool = False) -> CelestrakClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if empty:
            return httpx.Response(200, text=json.dumps("No GP data found"))
        if dict(request.url.params).get("CATNR") == "25544":
            return httpx.Response(200, json=[CELESTRAK_GP_JSON[0]])
        return httpx.Response(200, json=CELESTRAK_GP_JSON)

    client = httpx.AsyncClient(
        base_url="https://celestrak.org", transport=httpx.MockTransport(handler)
    )
    return CelestrakClient(client=client, max_retries=2, backoff_base_s=0.0)


@pytest.fixture
def session_factory(db):
    return db  # db fixture yields the async_sessionmaker directly


@pytest.fixture
def service(session_factory):
    return IngestionService(
        swpc=make_swpc_client(),
        celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(session_factory),
        ephemeris_sink=DbEphemerisSink(session_factory),
    )


async def alert_count(factory: async_sessionmaker) -> int:
    async with factory() as session:
        return (await session.execute(sa.select(sa.func.count(Alert.id)))).scalar_one()


# -- clients ----------------------------------------------------------------


async def test_celestrak_parses_gp_group():
    records = await make_celestrak_client().get_group("active")
    assert len(records) == 2
    iss = records[0]
    assert iss.norad_cat_id == 25544
    assert iss.epoch.tzinfo is not None
    assert 92 < iss.approx_period_minutes < 93


async def test_celestrak_no_data_string_yields_empty():
    assert await make_celestrak_client(empty=True).get_group("nonexistent") == []


async def test_swpc_latest_kp_uses_newest_row_and_estimated_kp():
    reading = await make_swpc_client(storm=True).get_latest_kp()
    assert reading is not None
    assert reading.kp_index == pytest.approx(6.67)
    assert reading.time_tag.tzinfo is not None


async def test_swpc_solar_wind_combines_speed_and_imf():
    sw = await make_swpc_client().get_solar_wind()
    assert sw is not None
    assert sw.wind_speed_km_s == pytest.approx(812.3)
    assert sw.bz_nt == pytest.approx(-18.4)


async def test_retry_then_source_unavailable_on_5xx():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = BaseSourceClient(
        base_url="https://example.invalid",
        client=httpx.AsyncClient(
            base_url="https://example.invalid",
            transport=httpx.MockTransport(handler),
        ),
        max_retries=3,
        backoff_base_s=0.0,
    )
    with pytest.raises(SourceUnavailable):
        await client._get_json("/x")
    assert calls["n"] == 3  # retried


async def test_no_retry_on_404():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    client = BaseSourceClient(
        base_url="https://example.invalid",
        client=httpx.AsyncClient(
            base_url="https://example.invalid",
            transport=httpx.MockTransport(handler),
        ),
        max_retries=3,
        backoff_base_s=0.0,
    )
    with pytest.raises(SourceUnavailable):
        await client._get_json("/x")
    assert calls["n"] == 1  # non-transient, no retry


# -- severity policy --------------------------------------------------------


def test_kp_severity_thresholds():
    assert kp_severity(4.9) is None
    assert kp_severity(5.0) == AlertSeverity.HIGH
    assert kp_severity(6.9) == AlertSeverity.HIGH
    assert kp_severity(7.0) == AlertSeverity.CRITICAL


def test_wind_severity_thresholds():
    assert wind_severity(SolarWindSummary(time_tag=NOW, wind_speed_km_s=500)) is None
    assert wind_severity(SolarWindSummary(time_tag=NOW, wind_speed_km_s=650)) == AlertSeverity.HIGH
    assert wind_severity(SolarWindSummary(time_tag=NOW, wind_speed_km_s=850)) == AlertSeverity.CRITICAL
    assert wind_severity(SolarWindSummary(time_tag=NOW, bz_nt=-12)) == AlertSeverity.HIGH
    assert wind_severity(SolarWindSummary(time_tag=NOW, bz_nt=-20)) == AlertSeverity.CRITICAL


def test_bulletin_severity_mapping():
    assert bulletin_severity("WARNING: K-index 6") == AlertSeverity.MEDIUM
    assert bulletin_severity("WATCH: G2 predicted") == AlertSeverity.LOW
    assert bulletin_severity("SUMMARY: quiet conditions") == AlertSeverity.INFO


# -- service + DB sinks -----------------------------------------------------


async def test_poll_kp_storm_writes_high_alert(service, session_factory):
    draft = await service.poll_kp()
    assert draft is not None and draft.severity == AlertSeverity.HIGH
    async with session_factory() as session:
        alert = (
            await session.execute(
                sa.select(Alert).where(Alert.dedupe_key == draft.dedupe_key)
            )
        ).scalar_one()
    assert alert.source == "swpc"
    assert alert.severity == AlertSeverity.HIGH


async def test_poll_kp_quiet_writes_nothing(session_factory):
    svc = IngestionService(
        swpc=make_swpc_client(storm=False),
        celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(session_factory),
    )
    assert await svc.poll_kp() is None
    assert await alert_count(session_factory) == 0


async def test_repeated_polls_same_bucket_dedupe(service, session_factory):
    await service.poll_kp()
    await service.poll_kp()
    await service.poll_kp()
    assert await alert_count(session_factory) == 1  # one alert per 3h bucket


async def test_poll_solar_wind_critical(service, session_factory):
    draft = await service.poll_solar_wind()
    assert draft is not None
    assert draft.severity == AlertSeverity.CRITICAL  # 812 km/s + Bz -18.4
    assert await alert_count(session_factory) == 1


async def test_poll_bulletins_severity_and_dedupe(service, session_factory):
    assert await service.poll_swpc_bulletins() == 2
    async with session_factory() as session:
        sevs = set(
            (await session.execute(sa.select(Alert.severity))).scalars()
        )
    assert AlertSeverity.MEDIUM in sevs and AlertSeverity.LOW in sevs
    # second pass fully deduped
    assert await service.poll_swpc_bulletins() == 0
    assert await alert_count(session_factory) == 2


async def test_fail_open_on_source_outage(session_factory):
    svc = IngestionService(
        swpc=make_swpc_client(fail=True),
        celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(session_factory),
    )
    assert await svc.poll_kp() is None
    assert await svc.poll_solar_wind() is None
    assert await svc.poll_swpc_bulletins() == 0
    assert await alert_count(session_factory) == 0


async def test_refresh_catalog_upserts_and_is_idempotent(service, session_factory):
    assert await service.refresh_catalog("active") == 2
    assert await service.refresh_catalog("active") == 2  # idempotent
    async with session_factory() as session:
        rows = list((await session.execute(sa.select(AssetEphemeris))).scalars())
    assert len(rows) == 2
    by_id = {r.norad_cat_id: r for r in rows}
    assert by_id[25544].object_name == "ISS (ZARYA)"
    assert by_id[25544].epoch.replace(tzinfo=timezone.utc) == datetime(
        2026, 7, 17, 12, 0, tzinfo=timezone.utc
    )


async def test_refresh_catalog_noop_without_sink(session_factory):
    svc = IngestionService(
        swpc=make_swpc_client(),
        celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(session_factory),
        ephemeris_sink=None,
    )
    assert await svc.refresh_catalog("active") == 0
