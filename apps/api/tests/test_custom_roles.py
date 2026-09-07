"""Phase 14 — custom roles, permission groups, approval workflows."""

from __future__ import annotations

from aegis_api.models.enums import Role


async def _mk_ws(client, headers, slug):
    r = await client.post(
        "/v1/workspaces".replace("/v1", "/api/v1"),
        json={"name": slug, "slug": slug},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_permission_catalog(client, admin):
    _, headers = admin
    r = await client.get("/api/v1/workspaces/rbac/catalog", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "response-actions" in body["groups"]
    assert "incidents:respond" in body["sensitive"]


async def test_non_sensitive_role_active_immediately(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "cr-a")
    r = await client.post(
        "/api/v1/workspaces/cr-a/roles",
        json={
            "name": "Fleet Viewer",
            "slug": "fleet-viewer",
            "groups": ["fleet-read", "reporting"],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"
    assert "assets:read" in r.json()["permission_values"]


async def test_sensitive_role_requires_second_admin(client, admin, make_user):
    _, headers = admin
    await _mk_ws(client, headers, "cr-b")

    r = await client.post(
        "/api/v1/workspaces/cr-b/roles",
        json={
            "name": "Responder Plus",
            "slug": "responder-plus",
            "groups": ["detections-triage", "response-actions"],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"

    # pending role cannot be assigned
    me_id = admin[0].id
    r = await client.put(
        f"/api/v1/workspaces/cr-b/members/{me_id}/custom-role",
        json={"role_slug": "responder-plus"},
        headers=headers,
    )
    assert r.status_code == 404

    # approval visible
    r = await client.get("/api/v1/workspaces/cr-b/approvals", headers=headers)
    assert r.status_code == 200 and len(r.json()) == 1
    approval_id = r.json()[0]["id"]
    assert r.json()[0]["payload"]["sensitive_permissions"] == ["incidents:respond"]

    # self-approval refused
    r = await client.post(
        f"/api/v1/workspaces/cr-b/approvals/{approval_id}",
        json={"approve": True},
        headers=headers,
    )
    assert r.status_code == 422
    assert "second admin" in r.json()["detail"]

    # a second platform admin approves
    _, second_headers = await make_user("second.admin@orbitalsentinel.io", Role.ADMIN)
    r = await client.post(
        f"/api/v1/workspaces/cr-b/approvals/{approval_id}",
        json={"approve": True, "reason": "SoD reviewed"},
        headers=second_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # role now active and assignable
    r = await client.get("/api/v1/workspaces/cr-b/roles", headers=headers)
    assert r.json()[0]["status"] == "active"
    r = await client.put(
        f"/api/v1/workspaces/cr-b/members/{me_id}/custom-role",
        json={"role_slug": "responder-plus"},
        headers=headers,
    )
    assert r.status_code == 204


async def test_rejected_role_stays_unusable(client, admin, make_user):
    me, headers = admin
    await _mk_ws(client, headers, "cr-c")
    r = await client.post(
        "/api/v1/workspaces/cr-c/roles",
        json={"name": "Audit Peek", "slug": "audit-peek", "groups": ["governance"]},
        headers=headers,
    )
    assert r.json()["status"] == "pending"
    r = await client.get("/api/v1/workspaces/cr-c/approvals", headers=headers)
    approval_id = r.json()[0]["id"]

    _, second_headers = await make_user("second2.admin@orbitalsentinel.io", Role.ADMIN)
    r = await client.post(
        f"/api/v1/workspaces/cr-c/approvals/{approval_id}",
        json={"approve": False, "reason": "not justified"},
        headers=second_headers,
    )
    assert r.json()["status"] == "rejected"

    r = await client.put(
        f"/api/v1/workspaces/cr-c/members/{me.id}/custom-role",
        json={"role_slug": "audit-peek"},
        headers=headers,
    )
    assert r.status_code == 404  # rejected == unusable, same as unknown


async def test_custom_role_grants_permission_via_workspace(client, admin, make_user):
    """A viewer with an approved custom 'governance' role can read audit
    logs — but only inside the workspace that granted it."""
    _, admin_headers = admin
    await _mk_ws(client, admin_headers, "cr-d")

    limited, limited_headers = await make_user("limited@orbitalsentinel.io", Role.VIEWER)
    r = await client.post(
        "/api/v1/workspaces/cr-d/members",
        json={"user_id": str(limited.id), "role": "viewer"},
        headers=admin_headers,
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/workspaces/cr-d/roles",
        json={"name": "Compliance", "slug": "compliance", "groups": ["governance"]},
        headers=admin_headers,
    )
    approval = (
        await client.get("/api/v1/workspaces/cr-d/approvals", headers=admin_headers)
    ).json()[0]
    _, second_headers = await make_user("second3.admin@orbitalsentinel.io", Role.ADMIN)
    await client.post(
        f"/api/v1/workspaces/cr-d/approvals/{approval['id']}",
        json={"approve": True},
        headers=second_headers,
    )
    r = await client.put(
        f"/api/v1/workspaces/cr-d/members/{limited.id}/custom-role",
        json={"role_slug": "compliance"},
        headers=admin_headers,
    )
    assert r.status_code == 204

    # Without workspace context: denied
    r = await client.get("/api/v1/audit", headers=limited_headers)
    assert r.status_code == 403

    # With the granting workspace active: allowed
    r = await client.get("/api/v1/audit", headers={**limited_headers, "X-Workspace": "cr-d"})
    assert r.status_code == 200, r.text


async def test_unknown_group_rejected(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "cr-e")
    r = await client.post(
        "/api/v1/workspaces/cr-e/roles",
        json={"name": "X", "slug": "x-role", "groups": ["not-a-group"]},
        headers=headers,
    )
    assert r.status_code == 422
    assert "Unknown permission group" in r.json()["detail"]
