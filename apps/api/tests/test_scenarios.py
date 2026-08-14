"""Saved Digital Twin scenarios: persistence, replay parity, RBAC."""

from tests.conftest import SAT, create_asset

MISSION = {"name": "SCENARIO-WATCH", "priority": "critical", "status": "active"}


async def _mission_with_sat(client, headers):
    mission = (await client.post("/api/v1/missions", json=MISSION, headers=headers)).json()
    sat = await create_asset(client, headers, SAT)
    await client.post(
        f"/api/v1/missions/{mission['id']}/assets",
        json={"asset_id": sat["id"], "dependency_criticality": "critical"},
        headers=headers,
    )
    return mission, sat


async def test_create_list_and_get_scenario(client, operator):
    _, headers = operator
    _, sat = await _mission_with_sat(client, headers)

    body = {
        "name": "Primary sat loss",
        "description": "What if SENTRY-7 goes offline?",
        "perturbations": [{"kind": "offline", "asset_id": sat["id"]}],
    }
    created = (
        await client.post("/api/v1/digital-twin/scenarios", json=body, headers=headers)
    ).json()
    assert created["name"] == "Primary sat loss"
    assert created["perturbations"][0]["kind"] == "offline"
    assert created["last_run_at"] is None

    listed = (await client.get("/api/v1/digital-twin/scenarios", headers=headers)).json()
    assert any(s["id"] == created["id"] for s in listed)

    fetched = (
        await client.get(f"/api/v1/digital-twin/scenarios/{created['id']}", headers=headers)
    ).json()
    assert fetched["description"] == "What if SENTRY-7 goes offline?"


async def test_run_scenario_reproduces_adhoc_simulation(client, operator):
    """A saved scenario, when run, must produce the same projection as the
    equivalent ad-hoc simulate call — proving persistence is faithful."""
    _, headers = operator
    _, sat = await _mission_with_sat(client, headers)
    perturbations = [{"kind": "offline", "asset_id": sat["id"]}]

    adhoc = (
        await client.post(
            "/api/v1/digital-twin/simulate",
            json={"name": "Primary sat loss", "perturbations": perturbations},
            headers=headers,
        )
    ).json()

    created = (
        await client.post(
            "/api/v1/digital-twin/scenarios",
            json={"name": "Primary sat loss", "perturbations": perturbations},
            headers=headers,
        )
    ).json()
    ran = (
        await client.post(f"/api/v1/digital-twin/scenarios/{created['id']}/run", headers=headers)
    ).json()

    assert ran["projected_average"] == adhoc["projected_average"]
    assert ran["average_delta"] == adhoc["average_delta"]
    assert ran["newly_at_risk"] == adhoc["newly_at_risk"]
    assert [m["projected_score"] for m in ran["missions"]] == [
        m["projected_score"] for m in adhoc["missions"]
    ]


async def test_running_scenario_stamps_last_run(client, operator):
    _, headers = operator
    _, sat = await _mission_with_sat(client, headers)
    created = (
        await client.post(
            "/api/v1/digital-twin/scenarios",
            json={"name": "x", "perturbations": [{"kind": "offline", "asset_id": sat["id"]}]},
            headers=headers,
        )
    ).json()
    assert created["last_run_at"] is None
    await client.post(f"/api/v1/digital-twin/scenarios/{created['id']}/run", headers=headers)
    after = (
        await client.get(f"/api/v1/digital-twin/scenarios/{created['id']}", headers=headers)
    ).json()
    assert after["last_run_at"] is not None


async def test_delete_scenario(client, operator):
    _, headers = operator
    _, sat = await _mission_with_sat(client, headers)
    created = (
        await client.post(
            "/api/v1/digital-twin/scenarios",
            json={"name": "temp", "perturbations": [{"kind": "offline", "asset_id": sat["id"]}]},
            headers=headers,
        )
    ).json()
    assert (
        await client.delete(f"/api/v1/digital-twin/scenarios/{created['id']}", headers=headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/digital-twin/scenarios/{created['id']}", headers=headers)
    ).status_code == 404


async def test_multi_perturbation_scenario_round_trips(client, operator):
    _, headers = operator
    _, sat = await _mission_with_sat(client, headers)
    perturbations = [
        {"kind": "set_status", "asset_id": sat["id"], "status": "degraded"},
        {"kind": "add_alerts", "asset_id": sat["id"], "magnitude": 4},
    ]
    created = (
        await client.post(
            "/api/v1/digital-twin/scenarios",
            json={"name": "degrade + alerts", "perturbations": perturbations},
            headers=headers,
        )
    ).json()
    assert len(created["perturbations"]) == 2
    # runs without error and reflects both perturbations
    ran = (
        await client.post(f"/api/v1/digital-twin/scenarios/{created['id']}/run", headers=headers)
    ).json()
    assert ran["average_delta"] < 0


async def test_viewer_cannot_create_or_run_scenarios(client, viewer, operator):
    op_user, op_headers = operator
    _, sat = await _mission_with_sat(client, op_headers)
    scenario = (
        await client.post(
            "/api/v1/digital-twin/scenarios",
            json={"name": "s", "perturbations": [{"kind": "offline", "asset_id": sat["id"]}]},
            headers=op_headers,
        )
    ).json()

    _, view_headers = viewer
    assert (
        await client.post(
            "/api/v1/digital-twin/scenarios",
            json={"name": "nope", "perturbations": []},
            headers=view_headers,
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/v1/digital-twin/scenarios/{scenario['id']}/run", headers=view_headers
        )
    ).status_code == 403
    # but viewers can read the library
    assert (
        await client.get("/api/v1/digital-twin/scenarios", headers=view_headers)
    ).status_code == 200
