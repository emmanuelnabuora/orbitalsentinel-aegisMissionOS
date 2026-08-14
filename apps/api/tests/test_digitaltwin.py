"""Digital Twin: what-if simulation, scoring parity, and read-only guarantee."""

from tests.conftest import GROUND, SAT, create_asset

MISSION = {"name": "TWIN-WATCH", "priority": "critical", "status": "active"}


async def _mission(client, headers, sat_crit="critical", ground_crit="high"):
    mission = (await client.post("/api/v1/missions", json=MISSION, headers=headers)).json()
    sat = await create_asset(client, headers, SAT)
    ground = await create_asset(client, headers, GROUND)
    for a, crit in ((sat, sat_crit), (ground, ground_crit)):
        await client.post(
            f"/api/v1/missions/{mission['id']}/assets",
            json={"asset_id": a["id"], "dependency_criticality": crit},
            headers=headers,
        )
    return mission, sat, ground


async def test_baseline_matches_missioniq_live_score(client, operator):
    """The twin's baseline must equal the live MissionIQ score exactly."""
    _, headers = operator
    mission, sat, _ = await _mission(client, headers)

    live = (await client.get(f"/api/v1/missioniq/missions/{mission['id']}", headers=headers)).json()

    # A no-op-ish perturbation on an unrelated dimension still reports baseline.
    sim = (
        await client.post(
            "/api/v1/digital-twin/simulate",
            json={
                "name": "parity check",
                "perturbations": [{"kind": "add_alerts", "asset_id": sat["id"], "magnitude": 0}],
            },
            headers=headers,
        )
    ).json()

    proj = next(m for m in sim["missions"] if m["mission_id"] == mission["id"])
    assert proj["baseline_score"] == live["score"]
    assert proj["baseline_health"] == live["health"]


async def test_offline_critical_asset_drops_assurance(client, operator):
    _, headers = operator
    mission, sat, _ = await _mission(client, headers)

    sim = (
        await client.post(
            "/api/v1/digital-twin/simulate",
            json={
                "name": "SENTRY-7 loss",
                "perturbations": [{"kind": "offline", "asset_id": sat["id"]}],
            },
            headers=headers,
        )
    ).json()

    proj = next(m for m in sim["missions"] if m["mission_id"] == mission["id"])
    assert proj["baseline_score"] == 100
    # critical asset offline = -45
    assert proj["projected_score"] == 55
    assert proj["delta"] == -45
    assert sim["average_delta"] == -45
    assert any(i["projected_status"] == "offline" for i in sim["impacted_assets"])


async def test_scenario_pushes_mission_into_at_risk(client, operator):
    _, headers = operator
    mission, sat, ground = await _mission(client, headers)

    # Offline the critical sat (-45) AND degrade the high ground station
    # (22 * 0.75 = -16.5 -> -17) => 100 - 45 - 17 = ~38 => at_risk.
    sim = (
        await client.post(
            "/api/v1/digital-twin/simulate",
            json={
                "name": "northern corridor blackout",
                "perturbations": [
                    {"kind": "offline", "asset_id": sat["id"]},
                    {"kind": "set_status", "asset_id": ground["id"], "status": "degraded"},
                ],
            },
            headers=headers,
        )
    ).json()

    proj = next(m for m in sim["missions"] if m["mission_id"] == mission["id"])
    assert proj["projected_health"] == "at_risk"
    assert proj["crossed_threshold"] is True
    assert "TWIN-WATCH" in sim["newly_at_risk"]
    assert sim["missions_at_risk_after"] == 1
    assert sim["missions_at_risk_before"] == 0


async def test_remove_asset_excludes_it_from_scoring(client, operator):
    _, headers = operator
    mission, sat, ground = await _mission(client, headers)

    sim = (
        await client.post(
            "/api/v1/digital-twin/simulate",
            json={
                "name": "sat destroyed",
                "perturbations": [{"kind": "remove_asset", "asset_id": sat["id"]}],
            },
            headers=headers,
        )
    ).json()

    # With the sat gone and the ground station operational, the remaining
    # mission has no penalties -> back to 100 (removal drops its contribution).
    proj = next(m for m in sim["missions"] if m["mission_id"] == mission["id"])
    assert proj["projected_score"] == 100
    assert any(i["removed"] for i in sim["impacted_assets"])


async def test_simulation_does_not_mutate_real_data(client, operator):
    _, headers = operator
    mission, sat, _ = await _mission(client, headers)

    await client.post(
        "/api/v1/digital-twin/simulate",
        json={
            "name": "destructive?",
            "perturbations": [
                {"kind": "offline", "asset_id": sat["id"]},
                {"kind": "add_alerts", "asset_id": sat["id"], "magnitude": 5},
            ],
        },
        headers=headers,
    )

    # Real asset status unchanged
    asset = (await client.get(f"/api/v1/assets/{sat['id']}", headers=headers)).json()
    assert asset["status"] == "operational"
    # No real alerts created
    alerts = (await client.get(f"/api/v1/alerts?asset_id={sat['id']}", headers=headers)).json()
    assert alerts["total"] == 0
    # Live MissionIQ score still pristine
    live = (await client.get(f"/api/v1/missioniq/missions/{mission['id']}", headers=headers)).json()
    assert live["score"] == 100


async def test_add_alerts_perturbation_applies_penalty(client, operator):
    _, headers = operator
    mission, sat, _ = await _mission(client, headers)

    sim = (
        await client.post(
            "/api/v1/digital-twin/simulate",
            json={
                "name": "alert storm",
                "perturbations": [{"kind": "add_alerts", "asset_id": sat["id"], "magnitude": 3}],
            },
            headers=headers,
        )
    ).json()

    proj = next(m for m in sim["missions"] if m["mission_id"] == mission["id"])
    # 3 alerts * 6 * 1.0 (critical weight) = -18
    assert proj["projected_score"] == 82
    assert proj["delta"] == -18


async def test_unknown_asset_is_rejected(client, operator):
    _, headers = operator
    await _mission(client, headers)
    import uuid

    resp = await client.post(
        "/api/v1/digital-twin/simulate",
        json={
            "name": "typo",
            "perturbations": [{"kind": "offline", "asset_id": str(uuid.uuid4())}],
        },
        headers=headers,
    )
    assert resp.status_code == 404


async def test_viewer_cannot_simulate(client, viewer):
    _, headers = viewer
    import uuid

    resp = await client.post(
        "/api/v1/digital-twin/simulate",
        json={
            "name": "x",
            "perturbations": [{"kind": "offline", "asset_id": str(uuid.uuid4())}],
        },
        headers=headers,
    )
    assert resp.status_code == 403
