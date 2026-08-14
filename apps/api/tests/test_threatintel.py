"""Threat Intelligence: ingestion, correlation into the alert pipeline, feeds."""

import httpx
from tests.conftest import create_asset

from aegis_api.services.threatintel.engine import ThreatIntelService
from aegis_api.services.threatintel.feeds import JSONFeedProvider


async def _persist_user(session):
    """Create a committed user in the caller's session for audit FK integrity."""
    from aegis_api.models.enums import Role
    from aegis_api.services.users import UserService

    return await UserService(session).create(
        email="feed-actor@orbitalsentinel.io",
        password="correct horse battery staple",
        full_name="Feed Actor",
        roles=[Role.ANALYST],
        actor_id=None,
    )


# An asset whose attributes contain a known-bad indicator value.
TAINTED_ASSET = {
    "name": "Edge Relay Node",
    "asset_type": "network",
    "criticality": "high",
    "status": "operational",
    "attributes": {"mgmt_ip": "203.0.113.66", "region": "us-gov-west-1"},
}


async def test_ingest_curated_feed_is_idempotent(client, operator):
    _, headers = operator

    first = (await client.post("/api/v1/threat-intel/ingest", headers=headers)).json()
    assert first[0]["source"] == "aegis-curated"
    assert first[0]["created"] > 0
    assert first[0]["updated"] == 0

    # second ingest updates, never duplicates
    second = (await client.post("/api/v1/threat-intel/ingest", headers=headers)).json()
    assert second[0]["created"] == 0
    assert second[0]["updated"] == first[0]["created"]

    summary = (await client.get("/api/v1/threat-intel/summary", headers=headers)).json()
    assert summary["active_indicators"] == first[0]["created"]
    assert "aegis-curated" in summary["sources"]


async def test_correlation_raises_alert_into_pipeline(client, operator):
    _, headers = operator
    await create_asset(client, headers, TAINTED_ASSET)
    await client.post("/api/v1/threat-intel/ingest", headers=headers)

    result = (await client.post("/api/v1/threat-intel/correlate", headers=headers)).json()
    assert result["new_matches"] == 1
    assert result["alerts_raised"] == 1
    match = result["matches"][0]
    assert match["indicator_value"] == "203.0.113.66"
    assert match["matched_on"] == "mgmt_ip"
    assert match["asset_name"] == "Edge Relay Node"

    # the raised alert is a first-class alert in the normal pipeline
    alerts = (await client.get("/api/v1/alerts?severity=critical", headers=headers)).json()
    ti_alerts = [a for a in alerts["items"] if a["source"] == "ThreatIntel"]
    assert len(ti_alerts) == 1
    assert ti_alerts[0]["asset_name"] == "Edge Relay Node"
    assert ti_alerts[0]["id"] == match["alert_id"]


async def test_correlation_is_idempotent(client, operator):
    _, headers = operator
    await create_asset(client, headers, TAINTED_ASSET)
    await client.post("/api/v1/threat-intel/ingest", headers=headers)

    first = (await client.post("/api/v1/threat-intel/correlate", headers=headers)).json()
    assert first["new_matches"] == 1
    # re-running raises no duplicate match or alert
    second = (await client.post("/api/v1/threat-intel/correlate", headers=headers)).json()
    assert second["new_matches"] == 0
    assert second["alerts_raised"] == 0

    matches = (await client.get("/api/v1/threat-intel/matches", headers=headers)).json()
    assert len(matches) == 1


async def test_clean_assets_produce_no_matches(client, operator):
    _, headers = operator
    await create_asset(client, headers)  # default SENTRY-7, no tainted attrs
    await client.post("/api/v1/threat-intel/ingest", headers=headers)
    result = (await client.post("/api/v1/threat-intel/correlate", headers=headers)).json()
    assert result["new_matches"] == 0


async def test_viewer_cannot_ingest_or_correlate(client, viewer):
    _, headers = viewer
    assert (await client.post("/api/v1/threat-intel/ingest", headers=headers)).status_code == 403
    assert (await client.post("/api/v1/threat-intel/correlate", headers=headers)).status_code == 403
    # but viewers can read intel
    assert (await client.get("/api/v1/threat-intel/summary", headers=headers)).status_code == 200


async def test_manual_indicator_registration_and_search(client, operator):
    _, headers = operator
    body = {
        "indicator_type": "domain",
        "value": "malicious-uplink.invalid",
        "category": "c2",
        "severity": "high",
        "confidence": 90,
        "description": "Operator-reported C2 domain.",
    }
    created = (
        await client.post("/api/v1/threat-intel/indicators", json=body, headers=headers)
    ).json()
    assert created["source"] == "manual"

    found = (
        await client.get("/api/v1/threat-intel/indicators?search=uplink", headers=headers)
    ).json()
    assert found["total"] == 1
    assert found["items"][0]["value"] == "malicious-uplink.invalid"


async def test_json_feed_provider_maps_fields(db):
    """Generic JSON feed ingestion against a stubbed HTTP endpoint."""
    feed_payload = [
        {"ioc": "198.51.100.99", "kind": "ip", "threat": "scanner", "sev": "medium"},
        {"ioc": "bad.invalid", "kind": "domain", "threat": "phishing", "sev": "high"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=feed_payload)

    provider = JSONFeedProvider(
        name="acme-osint",
        url="https://feed.acme.invalid/iocs.json",
        field_map={
            "value": "ioc",
            "indicator_type": "kind",
            "category": "threat",
            "severity": "sev",
        },
        defaults={"confidence": 60},
        transport=httpx.MockTransport(handler),
    )

    async with db() as session:
        # A real user: audit records carry an actor FK enforced by Postgres.
        actor = await _persist_user(session)
        svc = ThreatIntelService(session, providers=[provider])
        results = await svc.ingest(actor_id=actor.id)
        assert results[0].source == "acme-osint"
        assert results[0].created == 2
        indicators, total = await svc.list_indicators(limit=10, offset=0)
        assert total == 2
        assert {i.value for i in indicators} == {"198.51.100.99", "bad.invalid"}
        assert all(i.confidence == 60 for i in indicators)
