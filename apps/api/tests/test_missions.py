from tests.conftest import GROUND, SAT, create_asset

MISSION = {
    "name": "OVERWATCH-ALPHA",
    "priority": "critical",
    "status": "active",
    "description": "Persistent comms coverage, northern corridor",
}


async def create_mission(client, headers):
    resp = await client.post("/api/v1/missions", json=MISSION, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_mission_crud_and_ownership(client, operator):
    user, headers = operator
    mission = await create_mission(client, headers)
    assert mission["owner_id"] == str(user.id)

    resp = await client.patch(
        f"/api/v1/missions/{mission['id']}", json={"status": "degraded"}, headers=headers
    )
    assert resp.json()["status"] == "degraded"


async def test_attach_detach_and_duplicate_conflict(client, operator):
    _, headers = operator
    mission = await create_mission(client, headers)
    asset = await create_asset(client, headers)

    attach = {"asset_id": asset["id"], "dependency_criticality": "critical"}
    assert (
        await client.post(f"/api/v1/missions/{mission['id']}/assets", json=attach, headers=headers)
    ).status_code == 201
    # duplicate attach -> 409
    assert (
        await client.post(f"/api/v1/missions/{mission['id']}/assets", json=attach, headers=headers)
    ).status_code == 409

    listed = await client.get(f"/api/v1/missions/{mission['id']}/assets", headers=headers)
    assert listed.json()[0]["asset"]["name"] == "SENTRY-7"
    assert listed.json()[0]["dependency_criticality"] == "critical"

    assert (
        await client.delete(
            f"/api/v1/missions/{mission['id']}/assets/{asset['id']}", headers=headers
        )
    ).status_code == 204


async def test_mission_graph_includes_asset_dependencies(client, operator):
    _, headers = operator
    mission = await create_mission(client, headers)
    sat = await create_asset(client, headers, SAT)
    ground = await create_asset(client, headers, GROUND)

    for asset_id in (sat["id"], ground["id"]):
        await client.post(
            f"/api/v1/missions/{mission['id']}/assets",
            json={"asset_id": asset_id, "dependency_criticality": "high"},
            headers=headers,
        )
    # satellite depends on its ground station
    await client.post(
        f"/api/v1/assets/{sat['id']}/dependencies",
        json={"depends_on_id": ground["id"], "criticality": "critical"},
        headers=headers,
    )

    graph = (await client.get(f"/api/v1/missions/{mission['id']}/graph", headers=headers)).json()
    kinds = {n["kind"] for n in graph["nodes"]}
    assert kinds == {"mission", "asset"}
    assert len(graph["nodes"]) == 3

    edge_kinds = sorted(e["kind"] for e in graph["edges"])
    assert edge_kinds == ["asset_dependency", "mission_dependency", "mission_dependency"]
    asset_edge = next(e for e in graph["edges"] if e["kind"] == "asset_dependency")
    assert asset_edge["source"] == sat["id"]
    assert asset_edge["target"] == ground["id"]
    assert asset_edge["criticality"] == "critical"


async def test_unknown_mission_is_404(client, viewer):
    _, headers = viewer
    resp = await client.get(
        "/api/v1/missions/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert resp.status_code == 404
