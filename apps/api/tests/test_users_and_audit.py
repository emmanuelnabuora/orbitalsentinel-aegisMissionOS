import sqlalchemy as sa
from tests.conftest import create_asset

from aegis_api.models.audit import AuditLog


async def test_only_admin_creates_users(client, admin, operator):
    _, admin_headers = admin
    _, op_headers = operator
    payload = {
        "email": "analyst@orbitalsentinel.io",
        "password": "a-long-password-123",
        "full_name": "New Analyst",
        "roles": ["analyst"],
    }
    assert (await client.post("/api/v1/users", json=payload, headers=op_headers)).status_code == 403

    resp = await client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    assert resp.json()["roles"] == ["analyst"]

    # duplicate email -> 409
    assert (
        await client.post("/api/v1/users", json=payload, headers=admin_headers)
    ).status_code == 409


async def test_short_password_rejected(client, admin):
    _, headers = admin
    payload = {
        "email": "x@orbitalsentinel.io",
        "password": "short",
        "full_name": "X",
        "roles": ["viewer"],
    }
    assert (await client.post("/api/v1/users", json=payload, headers=headers)).status_code == 422


async def test_mutations_are_audited_with_actor_and_request_id(client, operator, db):
    user, headers = operator
    asset = await create_asset(client, headers)
    await client.patch(
        f"/api/v1/assets/{asset['id']}",
        json={"status": "offline"},
        headers={**headers, "X-Request-ID": "audit-corr-1"},
    )

    async with db() as session:
        rows = list(
            (await session.execute(sa.select(AuditLog).order_by(AuditLog.created_at))).scalars()
        )
    actions = [r.action for r in rows]
    assert "user.created" in actions
    assert "asset.created" in actions
    assert "asset.updated" in actions

    updated = next(r for r in rows if r.action == "asset.updated")
    assert updated.actor_id == user.id
    assert updated.resource_id == asset["id"]
    assert updated.request_id == "audit-corr-1"
    assert updated.detail == {"fields": ["status"]}
