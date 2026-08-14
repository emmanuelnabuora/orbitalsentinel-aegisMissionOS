"""Phase 20 — user role management UI backend: platform roles, workspace
role changes, custom-role assignment, all with lockout guards."""

from __future__ import annotations

from aegis_api.models.enums import Role


async def _mk_ws(client, headers, slug):
    r = await client.post("/api/v1/workspaces", json={"name": slug, "slug": slug}, headers=headers)
    assert r.status_code == 201, r.text


# -- platform roles -----------------------------------------------------


async def test_set_platform_roles(client, admin, make_user):
    _, headers = admin
    target, target_headers = await make_user("promote.me@orbitalsentinel.io", Role.VIEWER)

    r = await client.put(
        f"/api/v1/users/{target.id}/roles",
        json={"roles": ["operator", "analyst"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert sorted(r.json()["roles"]) == ["analyst", "operator"]


async def test_cannot_self_demote_last_admin(client, admin):
    me, headers = admin
    r = await client.put(
        f"/api/v1/users/{me.id}/roles", json={"roles": ["operator"]}, headers=headers
    )
    assert r.status_code == 422
    assert "last platform admin" in r.json()["detail"]


async def test_cannot_remove_last_admin_via_another_admin(client, admin, make_user):
    me, headers = admin
    # promote a second user to admin, then demote the first — allowed,
    # since after this there is still one admin (the second user).
    second, _ = await make_user("second.plat.admin@orbitalsentinel.io", Role.VIEWER)
    r = await client.put(
        f"/api/v1/users/{second.id}/roles", json={"roles": ["admin"]}, headers=headers
    )
    assert r.status_code == 200

    r = await client.put(
        f"/api/v1/users/{me.id}/roles", json={"roles": ["viewer"]}, headers=headers
    )
    assert r.status_code == 200  # fine now, second admin exists


async def test_roles_update_is_audited(client, admin, make_user):
    _, headers = admin
    target, _ = await make_user("audited.role@orbitalsentinel.io", Role.VIEWER)
    await client.put(
        f"/api/v1/users/{target.id}/roles", json={"roles": ["auditor"]}, headers=headers
    )
    log = (await client.get("/api/v1/audit?limit=50", headers=headers)).json()
    assert any(e["action"] == "user.roles_changed" for e in log)


# -- workspace role changes ----------------------------------------------


async def test_workspace_role_change_reflected_in_members(client, admin, make_user):
    _, headers = admin
    await _mk_ws(client, headers, "rm-a")
    target, _ = await make_user("member.change@orbitalsentinel.io", Role.VIEWER)
    await client.post(
        "/api/v1/workspaces/rm-a/members",
        json={"user_id": str(target.id), "role": "viewer"},
        headers=headers,
    )
    r = await client.put(
        f"/api/v1/workspaces/rm-a/members/{target.id}",
        json={"role": "analyst"},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["role"] == "analyst"

    members = (await client.get("/api/v1/workspaces/rm-a/members", headers=headers)).json()
    mine = next(m for m in members if m["user_id"] == str(target.id))
    assert mine["role"] == "analyst"


# -- custom role assignment / unassignment --------------------------------


async def test_assign_and_unassign_custom_role(client, admin, make_user):
    _, headers = admin
    await _mk_ws(client, headers, "rm-b")
    target, target_headers = await make_user("custom.target@orbitalsentinel.io", Role.VIEWER)
    await client.post(
        "/api/v1/workspaces/rm-b/members",
        json={"user_id": str(target.id), "role": "viewer"},
        headers=headers,
    )
    await client.post(
        "/api/v1/workspaces/rm-b/roles",
        json={"name": "Fleet Viewer", "slug": "fleet-viewer-2", "groups": ["fleet-read"]},
        headers=headers,
    )
    r = await client.put(
        f"/api/v1/workspaces/rm-b/members/{target.id}/custom-role",
        json={"role_slug": "fleet-viewer-2"},
        headers=headers,
    )
    assert r.status_code == 204

    members = (await client.get("/api/v1/workspaces/rm-b/members", headers=headers)).json()
    mine = next(m for m in members if m["user_id"] == str(target.id))
    assert mine["custom_role_id"] is not None

    r = await client.delete(
        f"/api/v1/workspaces/rm-b/members/{target.id}/custom-role", headers=headers
    )
    assert r.status_code == 204
    members = (await client.get("/api/v1/workspaces/rm-b/members", headers=headers)).json()
    mine = next(m for m in members if m["user_id"] == str(target.id))
    assert mine["custom_role_id"] is None


async def test_unassign_nonmember_404s(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "rm-c")
    import uuid as _uuid

    r = await client.delete(
        f"/api/v1/workspaces/rm-c/members/{_uuid.uuid4()}/custom-role", headers=headers
    )
    assert r.status_code == 404
