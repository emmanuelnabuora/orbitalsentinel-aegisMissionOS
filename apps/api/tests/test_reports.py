"""Reporting: generation from live data across kinds, PDF export, RBAC."""

from tests.conftest import GROUND, SAT, create_asset

MISSION = {"name": "REPORT-RECON", "priority": "high", "status": "active"}


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
    return mission


async def test_executive_report_pulls_live_data(client, operator):
    _, headers = operator
    await _mission_with_assets(client, headers)

    resp = await client.post("/api/v1/reports", json={"kind": "executive"}, headers=headers)
    assert resp.status_code == 201
    report = resp.json()
    assert report["title"] == "Executive Mission Assurance Summary"
    assert report["content"]["summary"]
    headings = [s["heading"] for s in report["content"]["sections"]]
    assert "Overall Posture" in headings
    assert "Mission Assurance" in headings
    # the mission table row is present
    mission_section = next(
        s for s in report["content"]["sections"] if s["heading"] == "Mission Assurance"
    )
    assert any("REPORT-RECON" in row[0] for row in mission_section["rows"])


async def test_mission_assurance_report(client, operator):
    _, headers = operator
    await _mission_with_assets(client, headers)
    report = (
        await client.post("/api/v1/reports", json={"kind": "mission_assurance"}, headers=headers)
    ).json()
    assert any("REPORT-RECON" in s["heading"] for s in report["content"]["sections"])


async def test_incident_report_requires_subject(client, operator):
    _, headers = operator
    # missing subject_id → 422 validation failure
    resp = await client.post("/api/v1/reports", json={"kind": "incident"}, headers=headers)
    assert resp.status_code == 422


async def test_incident_report_generates_from_incident(client, operator):
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

    report = (
        await client.post(
            "/api/v1/reports",
            json={"kind": "incident", "subject_id": incident["id"]},
            headers=headers,
        )
    ).json()
    assert report["subject_id"] == incident["id"]
    headings = [s["heading"] for s in report["content"]["sections"]]
    assert "Timeline" in headings
    assert "Response Plan" in headings
    assert "Root-Cause Analysis" in headings


async def test_threat_intel_and_quantum_reports(client, operator):
    _, headers = operator
    await client.post("/api/v1/threat-intel/ingest", headers=headers)

    ti = (
        await client.post("/api/v1/reports", json={"kind": "threat_intel"}, headers=headers)
    ).json()
    assert any(s["heading"] == "Intelligence Overview" for s in ti["content"]["sections"])

    q = (
        await client.post("/api/v1/reports", json={"kind": "quantum_readiness"}, headers=headers)
    ).json()
    assert any(s["heading"] == "Readiness Overview" for s in q["content"]["sections"])


async def test_report_pdf_export(client, operator):
    _, headers = operator
    await _mission_with_assets(client, headers)
    report = (
        await client.post("/api/v1/reports", json={"kind": "executive"}, headers=headers)
    ).json()

    resp = await client.get(f"/api/v1/reports/{report['id']}/export.pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    # a real PDF
    assert resp.content[:5] == b"%PDF-"
    assert len(resp.content) > 1000


async def test_reports_are_listed_and_immutable_snapshots(client, operator):
    _, headers = operator
    await _mission_with_assets(client, headers)

    r1 = (await client.post("/api/v1/reports", json={"kind": "executive"}, headers=headers)).json()
    r2 = (await client.post("/api/v1/reports", json={"kind": "executive"}, headers=headers)).json()
    # regeneration creates a distinct snapshot, never mutates
    assert r1["id"] != r2["id"]

    listed = (await client.get("/api/v1/reports?kind=executive", headers=headers)).json()
    assert listed["total"] == 2

    # fetch by id returns the stored snapshot
    fetched = (await client.get(f"/api/v1/reports/{r1['id']}", headers=headers)).json()
    assert fetched["content"] == r1["content"]


async def test_viewer_cannot_generate_reports(client, viewer):
    _, headers = viewer
    resp = await client.post("/api/v1/reports", json={"kind": "executive"}, headers=headers)
    assert resp.status_code == 403
    # but can read/list
    assert (await client.get("/api/v1/reports", headers=headers)).status_code == 200
