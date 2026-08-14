"""Phase 18 — SOCRATES conjunction ingestion and auto-escalation."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import sqlalchemy as sa

from aegis_api.models.alert import Alert
from aegis_api.models.enums import AlertSeverity
from aegis_api.models.incident import Incident, IncidentEvent
from aegis_api.models.ingestion import AssetEphemeris
from aegis_api.services.ingestion.clients.socrates import SocratesClient
from aegis_api.services.ingestion.schemas import ConjunctionRecord
from aegis_api.services.ingestion.service import IngestionService, conjunction_severity
from aegis_api.services.ingestion.sinks import (
    DbAlertSink,
    DbIncidentSink,
    DbTrackedAssetLookup,
)
from tests.test_ingestion import make_celestrak_client, make_swpc_client

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)

SOCRATES_CSV = """NORAD_CAT_ID_1,OBJECT_NAME_1,NORAD_CAT_ID_2,OBJECT_NAME_2,TCA,TCA_RANGE,TCA_RELATIVE_SPEED,MAX_PROB
25544,ISS (ZARYA),90210,DEBRIS-A,2026-07-30 15:42:00,0.412,14.2,3.1e-4
61001,SENTINEL-DEMO 1,90211,DEBRIS-B,2026-07-30 18:10:00,3.900,11.7,4.0e-6
70001,OTHER-SAT,90212,DEBRIS-C,2026-07-30 19:00:00,0.700,13.0,2.0e-4
80001,FAR-SAT,90213,DEBRIS-D,2026-07-30 20:00:00,25.0,10.0,1.0e-9
"""


def make_socrates_client(csv_text: str = SOCRATES_CSV) -> SocratesClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=csv_text)

    client = httpx.AsyncClient(
        base_url="https://celestrak.org", transport=httpx.MockTransport(handler)
    )
    return SocratesClient(client=client, max_retries=2, backoff_base_s=0.0)


def _conj(**kw) -> ConjunctionRecord:
    base = dict(
        norad_cat_id_1=1, object_name_1="A", norad_cat_id_2=2, object_name_2="B",
        tca=NOW, min_range_km=10.0, relative_speed_km_s=10.0, max_probability=1e-9,
    )
    base.update(kw)
    return ConjunctionRecord(**base)


def test_conjunction_severity_thresholds():
    assert conjunction_severity(_conj(max_probability=2e-4)) == AlertSeverity.CRITICAL
    assert conjunction_severity(_conj(min_range_km=0.5)) == AlertSeverity.CRITICAL
    assert conjunction_severity(_conj(max_probability=5e-5)) == AlertSeverity.HIGH
    assert conjunction_severity(_conj(min_range_km=3.0)) == AlertSeverity.HIGH
    assert conjunction_severity(_conj(max_probability=5e-7)) == AlertSeverity.MEDIUM
    assert conjunction_severity(_conj()) is None  # 10 km, 1e-9


async def test_socrates_client_parses_csv():
    records = await make_socrates_client().get_conjunctions()
    assert len(records) == 4
    iss = records[0]
    assert iss.norad_cat_id_1 == 25544 and iss.min_range_km == 0.412
    assert iss.tca.tzinfo is not None


async def test_socrates_unrecognized_header_yields_empty():
    records = await make_socrates_client("foo,bar\n1,2\n").get_conjunctions()
    assert records == []


def make_service(db, with_tracked: bool = True) -> IngestionService:
    return IngestionService(
        swpc=make_swpc_client(),
        celestrak=make_celestrak_client(),
        alert_sink=DbAlertSink(db),
        socrates=make_socrates_client(),
        tracked_lookup=DbTrackedAssetLookup(db) if with_tracked else None,
        incident_sink=DbIncidentSink(db),
    )


async def _seed_tracked(db, *norad_ids: int):
    async with db() as session:
        for nid in norad_ids:
            session.add(AssetEphemeris(
                norad_cat_id=nid, object_name=f"OBJ-{nid}", object_id="X",
                epoch=NOW, mean_motion=15.0, eccentricity=0.0, inclination=51.0,
                ra_of_asc_node=0.0, arg_of_pericenter=0.0, mean_anomaly=0.0, bstar=0.0,
            ))
        await session.commit()


async def test_poll_creates_alerts_and_escalates_tracked_critical(db):
    await _seed_tracked(db, 25544, 61001)  # ISS + demo sat tracked; 70001 not
    svc = make_service(db)
    alerts, incidents = await svc.poll_conjunctions()
    # 3 rows meet severity (25544 CRIT, 61001 HIGH, 70001 CRIT); FAR-SAT none
    assert alerts == 3
    # only the tracked CRITICAL escalates: ISS. 70001 is critical but untracked;
    # 61001 tracked but HIGH.
    assert incidents == 1

    async with db() as session:
        incident = (await session.execute(sa.select(Incident))).scalar_one()
        assert incident.title.startswith("[AUTO] Conjunction: ISS")
        assert incident.severity == AlertSeverity.CRITICAL
        assert incident.commander_id is None
        linked = (
            await session.execute(
                sa.select(Alert).where(Alert.incident_id == incident.id)
            )
        ).scalar_one()
        assert linked.metadata_ if hasattr(linked, "metadata_") else True
        events = list((await session.execute(
            sa.select(IncidentEvent.kind).where(IncidentEvent.incident_id == incident.id)
        )).scalars())
        assert set(events) == {"created", "alert_linked"}


async def test_poll_is_idempotent(db):
    await _seed_tracked(db, 25544)
    svc = make_service(db)
    a1, i1 = await svc.poll_conjunctions()
    a2, i2 = await svc.poll_conjunctions()
    assert a1 == 3 and i1 == 1
    assert a2 == 0 and i2 == 0  # dedupe on (pair, TCA); no duplicate incidents
    async with db() as session:
        n = (await session.execute(sa.select(sa.func.count(Incident.id)))).scalar_one()
        assert n == 1


async def test_no_tracked_lookup_means_no_escalation(db):
    svc = make_service(db, with_tracked=False)
    alerts, incidents = await svc.poll_conjunctions()
    assert alerts == 3 and incidents == 0
