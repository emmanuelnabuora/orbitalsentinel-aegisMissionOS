"""Phase 15 — notifications and workspace preferences."""

from __future__ import annotations

from aegis_api.models.enums import Role


async def _mk_ws(client, headers, slug):
    r = await client.post("/api/v1/workspaces", json={"name": slug, "slug": slug}, headers=headers)
    assert r.status_code == 201, r.text


async def test_approval_flow_emits_notifications(client, admin, make_user):
    """Requesting a sensitive role notifies the OTHER admin; deciding
    notifies the requester."""
    me, my_headers = admin
    await _mk_ws(client, my_headers, "nt-a")
    other, other_headers = await make_user("other.admin@orbitalsentinel.io", Role.ADMIN)
    r = await client.post(
        "/api/v1/workspaces/nt-a/members",
        json={"user_id": str(other.id), "role": "admin"},
        headers=my_headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/workspaces/nt-a/roles",
        json={"name": "Keys", "slug": "keys-role", "groups": ["org-administration"]},
        headers=my_headers,
    )
    assert r.json()["status"] == "pending"

    # other admin got the request; requester did not self-notify
    inbox = (await client.get("/api/v1/notifications", headers=other_headers)).json()
    assert inbox["unread"] == 1
    assert inbox["items"][0]["kind"] == "approval.requested"
    mine = (await client.get("/api/v1/notifications", headers=my_headers)).json()
    assert mine["unread"] == 0

    approval_id = (await client.get("/api/v1/workspaces/nt-a/approvals", headers=my_headers)).json()[0]["id"]
    r = await client.post(
        f"/api/v1/workspaces/nt-a/approvals/{approval_id}",
        json={"approve": True, "reason": "ok"},
        headers=other_headers,
    )
    assert r.status_code == 200

    mine = (await client.get("/api/v1/notifications", headers=my_headers)).json()
    assert mine["unread"] == 1
    assert mine["items"][0]["kind"] == "approval.approved"


async def test_mark_read_and_read_all(client, admin, make_user):
    me, my_headers = admin
    await _mk_ws(client, my_headers, "nt-b")
    other, other_headers = await make_user("reader.admin@orbitalsentinel.io", Role.ADMIN)
    await client.post(
        "/api/v1/workspaces/nt-b/members",
        json={"user_id": str(other.id), "role": "admin"},
        headers=my_headers,
    )
    for i in range(2):
        await client.post(
            "/api/v1/workspaces/nt-b/roles",
            json={"name": f"R{i}", "slug": f"r{i}-role", "groups": ["governance"]},
            headers=my_headers,
        )
    inbox = (await client.get("/api/v1/notifications", headers=other_headers)).json()
    assert inbox["unread"] == 2
    nid = inbox["items"][0]["id"]
    r = await client.post(f"/api/v1/notifications/{nid}/read", headers=other_headers)
    assert r.status_code == 204
    assert (await client.get("/api/v1/notifications", headers=other_headers)).json()["unread"] == 1
    await client.post("/api/v1/notifications/read-all", headers=other_headers)
    assert (await client.get("/api/v1/notifications", headers=other_headers)).json()["unread"] == 0

    # cannot read someone else's notification
    r = await client.post(f"/api/v1/notifications/{nid}/read", headers=my_headers)
    assert r.status_code == 404


async def test_invite_redemption_notifies_inviter(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "nt-c")
    token = (await client.post(
        "/api/v1/workspaces/nt-c/invites",
        json={"email": "joiner@orbitalsentinel.space", "role": "viewer"},
        headers=headers,
    )).json()["token"]
    await client.post(
        "/api/v1/invites/redeem",
        json={"token": token, "password": "long enough password", "full_name": "Joiner"},
    )
    inbox = (await client.get("/api/v1/notifications", headers=headers)).json()
    kinds = [n["kind"] for n in inbox["items"]]
    assert "member.joined" in kinds


async def test_muted_kind_suppresses_emission(client, admin, make_user):
    me, my_headers = admin
    await _mk_ws(client, my_headers, "nt-d")
    other, other_headers = await make_user("muter.admin@orbitalsentinel.io", Role.ADMIN)
    await client.post(
        "/api/v1/workspaces/nt-d/members",
        json={"user_id": str(other.id), "role": "admin"},
        headers=my_headers,
    )
    # other admin mutes approval.requested in this workspace
    r = await client.put(
        "/api/v1/preferences",
        json={"data": {"muted_kinds": ["approval.requested"]}},
        headers={**other_headers, "X-Workspace": "nt-d"},
    )
    assert r.status_code == 200

    await client.post(
        "/api/v1/workspaces/nt-d/roles",
        json={"name": "Quiet", "slug": "quiet-role", "groups": ["governance"]},
        headers=my_headers,
    )
    inbox = (await client.get("/api/v1/notifications", headers=other_headers)).json()
    assert inbox["unread"] == 0  # muted


async def test_preferences_roundtrip_requires_workspace(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "nt-e")
    r = await client.get("/api/v1/preferences", headers=headers)
    assert r.status_code == 400  # no workspace selected
    r = await client.put(
        "/api/v1/preferences",
        json={"data": {"default": True, "dashboard": {"widgets": ["fleet", "alerts"]}}},
        headers={**headers, "X-Workspace": "nt-e"},
    )
    assert r.status_code == 200
    r = await client.get("/api/v1/preferences", headers={**headers, "X-Workspace": "nt-e"})
    assert r.json()["data"]["dashboard"]["widgets"] == ["fleet", "alerts"]
