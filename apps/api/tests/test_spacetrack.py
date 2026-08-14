"""Phase 22 — Space-Track.org client and Conjunction Data Message ingestion."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import sqlalchemy as sa

from aegis_api.models.alert import Alert
from aegis_api.models.enums import AlertSeverity
from aegis_api.models.incident import Incident
from aegis_api.services.ingestion.clients.base import SourceUnavailable
from aegis_api.services.ingestion.clients.spacetrack import CdmRecord, SpaceTrackClient
from aegis_api.services.ingestion.service import IngestionService
from aegis_api.services.ingestion.sinks import DbAlertSink, DbIncidentSink, DbTrackedAssetLookup
from aegis_api.models.ingestion import AssetEphemeris
from tests.test_ingestion import make_celestrak_client, make_swpc_client

CDM_ROW = {
    "CDM_ID": "000012345_conj_0000543",
    "TCA": "2026-08-01 03:15:00.000",
    "MISS_DISTANCE": "180.5",       # meters
    "RELATIVE_SPEED": "14200.0",    # meters/sec
    "COLLISION_PROBABILITY": "2.5e-4",
    "SAT1_OBJECT_DESIGNATOR": "25544",
    "SAT1_OBJECT_NAME": "ISS (ZARYA)",
    "SAT2_OBJECT_DESIGNATOR": "90210",
    "SAT2_OBJECT_NAME": "DEBRIS-A",
}

CDM_ROW_LOW_RISK = {
    "CDM_ID": "000099999_conj_0000001",
    "TCA": "2026-08-01 06:00:00.000",
    "MISS_DISTANCE": "25000.0",     # 25 km -> below all thresholds
    "RELATIVE_SPEED": "10000.0",
    "COLLISION_PROBABILITY": "1.0e-10",
    "SAT1_OBJECT_DESIGNATOR": "61001",
    "SAT1_OBJECT_NAME": "SENTINEL-DEMO 1",
    "SAT2_OBJECT_DESIGNATOR": "90211",
    "SAT2_OBJECT_NAME": "DEBRIS-B",
}


def make_spacetrack_client(
    *, cdm_rows=None, login_fails: bool = False, expire_session_once: bool = False
) -> SpaceTrackClient:
    rows = CDM_ROW_LOW_RISK.__class__ and (cdm_rows if cdm_rows is not None else [CDM_ROW])
    state = {"authed": False, "get_calls": 0, "expired_once": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ajaxauth/login":
            if login_fails:
                return httpx.Response(200, json={"Login": "Failed"})
            state["authed"] = True
            return httpx.Response(200, text="")
        if request.url.path.startswith("/basicspacedata/query/class/cdm"):
            state["get_calls"] += 1
            if expire_session_once and not state["expired_once"]:
                state["expired_once"] = True
                return httpx.Response(401, text="session expired")
            if not state["authed"]:
                return httpx.Response(401, text="not authenticated")
            return httpx.Response(200, json=rows)
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="https://www.space-track.org", transport=httpx.MockTransport(handler)
    )
    return SpaceTrackClient(
        "testuser", "testpass",
        client=client, max_retries=2, backoff_base_s=0.0, min_request_interval_s=0.0,
    )


# -- auth ---------------------------------------------------------------


async def test_login_then_fetch_succeeds():
    client = make_spacetrack_client()
    records = await client.get_cdms()
    assert len(records) == 1
    assert records[0].cdm_id == "000012345_conj_0000543"


async def test_bad_credentials_raise_source_unavailable():
    client = make_spacetrack_client(login_fails=True)
    try:
        await client.get_cdms()
        assert False, "expected SourceUnavailable"
    except SourceUnavailable:
        pass


async def test_expired_session_reauths_and_retries():
    client = make_spacetrack_client(expire_session_once=True)
    records = await client.get_cdms()
    assert len(records) == 1  # succeeded despite the mid-flight 401


# -- CDM parsing / unit conversion ---------------------------------------


def test_cdm_converts_meters_to_km():
    record = CdmRecord.from_raw(CDM_ROW)
    assert record is not None
    assert record.min_range_km == 180.5 / 1000.0
    assert record.relative_speed_km_s == 14200.0 / 1000.0
    assert record.max_probability == 2.5e-4
    assert record.norad_cat_id_1 == 25544
    assert record.norad_cat_id_2 == 90210
    assert record.tca.tzinfo is not None


def test_cdm_case_insensitive_and_malformed_rows_skipped():
    lower = {k.lower(): v for k, v in CDM_ROW.items()}
    assert CdmRecord.from_raw(lower) is not None

    missing_field = dict(CDM_ROW)
    del missing_field["MISS_DISTANCE"]
    assert CdmRecord.from_raw(missing_field) is None

    garbage = {"CDM_ID": "x"}
    assert CdmRecord.from_raw(garbage) is None


async def test_operator_gated_empty_result_is_not_an_error():
    """No registered satellites -> empty list, not an exception. This is
    expected Space-Track behavior, not a client bug."""
    client = make_spacetrack_client(cdm_rows=[])
    records = await client.get_cdms()
    assert records == []


# -- service integration: severity policy + escalation reused -----------


def make_service(db, *, cdm_rows=None) -> IngestionService:
    return IngestionService(
        swpc=make_swpc_client(),
        celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(db),
        spacetrack=make_spacetrack_client(cdm_rows=cdm_rows),
        tracked_lookup=DbTrackedAssetLookup(db),
        incident_sink=DbIncidentSink(db),
    )


async def _seed_tracked(db, *norad_ids: int):
    async with db() as session:
        for nid in norad_ids:
            session.add(AssetEphemeris(
                norad_cat_id=nid, object_name=f"OBJ-{nid}", object_id="X",
                epoch=datetime(2026, 8, 1, tzinfo=timezone.utc), mean_motion=15.0,
                eccentricity=0.0, inclination=51.0, ra_of_asc_node=0.0,
                arg_of_pericenter=0.0, mean_anomaly=0.0, bstar=0.0,
            ))
        await session.commit()


async def test_poll_cdms_creates_alert_and_escalates_tracked_critical(db):
    await _seed_tracked(db, 25544)  # ISS tracked; CDM_ROW's Pc=2.5e-4 -> CRITICAL
    svc = make_service(db, cdm_rows=[CDM_ROW])
    alerts, incidents = await svc.poll_cdms()
    assert alerts == 1
    assert incidents == 1

    async with db() as session:
        alert = (await session.execute(sa.select(Alert))).scalar_one()
        assert alert.source == "spacetrack"
        assert alert.severity == AlertSeverity.CRITICAL
        incident = (await session.execute(sa.select(Incident))).scalar_one()
        assert incident.commander_id is None
        assert alert.incident_id == incident.id


async def test_poll_cdms_low_risk_no_alert(db):
    svc = make_service(db, cdm_rows=[CDM_ROW_LOW_RISK])
    alerts, incidents = await svc.poll_cdms()
    assert alerts == 0 and incidents == 0


async def test_poll_cdms_idempotent(db):
    await _seed_tracked(db, 25544)
    svc = make_service(db, cdm_rows=[CDM_ROW])
    a1, i1 = await svc.poll_cdms()
    a2, i2 = await svc.poll_cdms()
    assert (a1, i1) == (1, 1)
    assert (a2, i2) == (0, 0)  # dedupe on CDM_ID


async def test_poll_cdms_noop_without_client(db):
    svc = IngestionService(
        swpc=make_swpc_client(), celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(db),
    )
    assert await svc.poll_cdms() == (0, 0)


async def test_socrates_and_spacetrack_dedupe_keys_never_collide(db):
    """Same physical conjunction reported by both sources should be
    treated as two distinct, independently-tracked alerts (different
    originating systems, potentially different Pc estimates) -- not
    silently deduped against each other."""
    await _seed_tracked(db, 25544)
    svc = make_service(db, cdm_rows=[CDM_ROW])
    await svc.poll_cdms()

    from tests.test_conjunctions import make_socrates_client

    svc._socrates = make_socrates_client()  # SOCRATES fixture includes ISS too
    await svc.poll_conjunctions()

    async with db() as session:
        keys = set((await session.execute(sa.select(Alert.dedupe_key))).scalars())
    assert any(k.startswith("spacetrack:cdm:") for k in keys)
    assert any(k.startswith("socrates:") for k in keys)
