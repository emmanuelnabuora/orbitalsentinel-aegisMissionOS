"""Alerts, Incidents, QuantumShield, MissionIQ, SentinelAI."""

from tests.conftest import GROUND, SAT, create_asset

MISSION = {"name": "OVERWATCH-ALPHA", "priority": "critical", "status": "active"}


async def _mission_with_assets(client, headers):
    mission = (await client.post("/api/v1/missions", json=MISSION, headers=headers)).json()
    sat = await create_asset(client, headers, SAT)
    ground = await create_asset(client, headers, GROUND)
    for a, crit in ((sat, "critical"), (ground, "high")):
        await client.post(
            f"/api/v1/missions/{mission['id']}/assets",
            json={"asset_id": a["id"], "dependency_criticality": crit},
            headers=headers,
        )
    return mission, sat, ground


async def test_alert_lifecycle_and_filters(client, operator, viewer):
    _, headers = operator
    _, view_headers = viewer
    asset = await create_asset(client, headers)

    resp = await client.post(
        "/api/v1/alerts",
        json={
            "title": "Telemetry signal anomaly on downlink",
            "severity": "high",
            "source": "SpaceShield",
            "asset_id": asset["id"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    alert = resp.json()
    assert alert["asset_name"] == "SENTRY-7"

    # viewer cannot create
    assert (
        await client.post(
            "/api/v1/alerts", json={"title": "x", "severity": "low"}, headers=view_headers
        )
    ).status_code == 403

    # filter by severity
    listed = (await client.get("/api/v1/alerts?severity=high", headers=view_headers)).json()
    assert listed["total"] == 1

    # assign + acknowledge
    user, _ = operator
    upd = await client.patch(
        f"/api/v1/alerts/{alert['id']}",
        json={"status": "acknowledged", "assigned_to": str(user.id)},
        headers=headers,
    )
    assert upd.json()["status"] == "acknowledged"
    assert upd.json()["assigned_to"] == str(user.id)


async def test_incident_timeline_and_linked_alerts(client, operator):
    _, headers = operator
    asset = await create_asset(client, headers)
    alert = (
        await client.post(
            "/api/v1/alerts",
            json={
                "title": "Certificate validation failure on ground link",
                "severity": "critical",
                "asset_id": asset["id"],
            },
            headers=headers,
        )
    ).json()

    incident = (
        await client.post(
            "/api/v1/incidents",
            json={
                "title": "Ground link trust chain failure",
                "severity": "critical",
                "alert_ids": [alert["id"]],
            },
            headers=headers,
        )
    ).json()

    await client.patch(
        f"/api/v1/incidents/{incident['id']}", json={"status": "investigating"}, headers=headers
    )
    await client.post(
        f"/api/v1/incidents/{incident['id']}/notes",
        json={"message": "Pulled cert chain for offline review."},
        headers=headers,
    )

    detail = (await client.get(f"/api/v1/incidents/{incident['id']}", headers=headers)).json()
    kinds = [e["kind"] for e in detail["events"]]
    assert kinds[0] == "created"
    assert "alert_linked" in kinds
    assert "status" in kinds
    assert "note" in kinds
    assert detail["alerts"][0]["id"] == alert["id"]


async def test_quantum_readiness_scoring(client, operator):
    _, headers = operator
    sat = await create_asset(client, headers, SAT)
    ground = await create_asset(client, headers, GROUND)

    records = [
        {
            "asset_id": ground["id"],
            "kind": "certificate",
            "algorithm": "RSA",
            "key_size": 2048,
            "subject": "CN=vandenberg.gs",
        },
        {"asset_id": ground["id"], "kind": "tls_endpoint", "algorithm": "ECDSA", "key_size": 256},
        {"asset_id": sat["id"], "kind": "data_at_rest", "algorithm": "AES-256-GCM"},
        {"asset_id": sat["id"], "kind": "tls_endpoint", "algorithm": "ML-KEM"},
    ]
    for r in records:
        assert (
            await client.post("/api/v1/quantum/inventory", json=r, headers=headers)
        ).status_code == 201

    q = (await client.get("/api/v1/quantum/readiness", headers=headers)).json()
    assert q["total_records"] == 4
    assert q["pqc_ready_records"] == 2
    assert q["vulnerable_records"] == 2
    assert q["score"] == 50
    assert q["vulnerable_by_algorithm"] == {"RSA": 1, "ECDSA": 1}
    assert q["exposed_assets"] == ["Vandenberg Ground Station"]
    assert any("ML-KEM" in r for r in q["recommendations"])


async def test_missioniq_scores_react_to_status_and_alerts(client, operator):
    _, headers = operator
    mission, sat, _ = await _mission_with_assets(client, headers)

    a1 = (await client.get(f"/api/v1/missioniq/missions/{mission['id']}", headers=headers)).json()
    assert a1["score"] == 100
    assert a1["health"] == "assured"

    # degrade the critical satellite + raise an alert on it
    await client.patch(f"/api/v1/assets/{sat['id']}", json={"status": "degraded"}, headers=headers)
    await client.post(
        "/api/v1/alerts",
        json={
            "title": "RF interference detected",
            "severity": "high",
            "asset_id": sat["id"],
        },
        headers=headers,
    )

    a2 = (await client.get(f"/api/v1/missioniq/missions/{mission['id']}", headers=headers)).json()
    assert a2["score"] < a1["score"]
    assert a2["degraded_assets"] == 1
    assert a2["open_alerts"] == 1
    assert any("degraded" in f for f in a2["factors"])

    fleet = (await client.get("/api/v1/missioniq/summary", headers=headers)).json()
    assert fleet["missions"][0]["mission_id"] == mission["id"]
    assert fleet["open_alerts"] == 1


async def test_sentinel_chat_is_data_grounded(client, operator):
    _, headers = operator
    await _mission_with_assets(client, headers)

    resp = await client.post(
        "/api/v1/sentinel/chat", json={"message": "What is our mission assurance?"}, headers=headers
    )
    body = resp.json()
    assert resp.status_code == 200
    assert "OVERWATCH-ALPHA" in body["answer"] or "assurance" in body["answer"]
    assert body["provider"] == "sentinel-rules-v1"
    assert body["suggested_actions"]


async def test_sentinel_incident_analysis_writes_timeline_event(client, operator):
    _, headers = operator
    asset = await create_asset(client, headers)
    alert = (
        await client.post(
            "/api/v1/alerts",
            json={
                "title": "Telemetry link dropout",
                "severity": "high",
                "asset_id": asset["id"],
            },
            headers=headers,
        )
    ).json()
    incident = (
        await client.post(
            "/api/v1/incidents",
            json={
                "title": "Downlink instability",
                "severity": "high",
                "alert_ids": [alert["id"]],
            },
            headers=headers,
        )
    ).json()

    analysis = (
        await client.post(f"/api/v1/sentinel/incidents/{incident['id']}/analyze", headers=headers)
    ).json()
    assert "Downlink instability" in analysis["summary"]
    assert any("Communications-path" in h for h in analysis["root_cause_hypotheses"])
    assert analysis["recommended_actions"]

    detail = (await client.get(f"/api/v1/incidents/{incident['id']}", headers=headers)).json()
    assert any(e["kind"] == "ai_analysis" for e in detail["events"])
