from tests.conftest import GROUND, SAT, create_asset


async def test_create_and_get_asset(client, operator, viewer):
    _, op_headers = operator
    _, view_headers = viewer
    asset = await create_asset(client, op_headers)
    assert asset["name"] == "SENTRY-7"
    assert asset["attributes"]["orbit"] == "LEO"

    resp = await client.get(f"/api/v1/assets/{asset['id']}", headers=view_headers)
    assert resp.status_code == 200


async def test_list_assets_with_filters(client, operator):
    _, headers = operator
    await create_asset(client, headers, SAT)
    await create_asset(client, headers, GROUND)

    resp = await client.get("/api/v1/assets?asset_type=satellite", headers=headers)
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["asset_type"] == "satellite"

    resp = await client.get("/api/v1/assets?search=vandenberg", headers=headers)
    assert resp.json()["total"] == 1


async def test_update_asset(client, operator):
    _, headers = operator
    asset = await create_asset(client, headers)
    resp = await client.patch(
        f"/api/v1/assets/{asset['id']}", json={"status": "degraded"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


async def test_viewer_cannot_mutate(client, operator, viewer):
    _, op_headers = operator
    _, view_headers = viewer
    asset = await create_asset(client, op_headers)

    assert (await client.post("/api/v1/assets", json=SAT, headers=view_headers)).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/assets/{asset['id']}", json={"status": "offline"}, headers=view_headers
        )
    ).status_code == 403


async def test_delete_requires_admin(client, operator, admin):
    _, op_headers = operator
    _, admin_headers = admin
    asset = await create_asset(client, op_headers)

    assert (
        await client.delete(f"/api/v1/assets/{asset['id']}", headers=op_headers)
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/assets/{asset['id']}", headers=admin_headers)
    ).status_code == 204
    assert (
        await client.get(f"/api/v1/assets/{asset['id']}", headers=admin_headers)
    ).status_code == 404


async def test_self_dependency_rejected(client, operator):
    _, headers = operator
    asset = await create_asset(client, headers)
    resp = await client.post(
        f"/api/v1/assets/{asset['id']}/dependencies",
        json={"depends_on_id": asset["id"]},
        headers=headers,
    )
    assert resp.status_code == 422
