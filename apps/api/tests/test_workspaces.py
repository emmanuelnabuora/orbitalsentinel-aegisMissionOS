"""Phase 12 — workspaces, tenancy, invites, service accounts, API keys."""

from __future__ import annotations

from aegis_api.models.enums import Role


async def _mk_ws(client, headers, slug, name="WS"):
    r = await client.post("/api/v1/workspaces", json={"name": name, "slug": slug}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_workspace_create_and_membership(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "orbitalsentinel", "OrbitalSentinel")
    r = await client.get("/api/v1/workspaces", headers=headers)
    assert [w["slug"] for w in r.json()] == ["orbitalsentinel"]


async def test_workspace_slug_conflict(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "aegis-ws")
    r = await client.post(
        "/api/v1/workspaces", json={"name": "B", "slug": "aegis-ws"}, headers=headers
    )
    assert r.status_code == 409


async def test_tenancy_scopes_assets(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "ws-a")
    await _mk_ws(client, headers, "ws-b")

    body = {
        "name": "SAT-A",
        "asset_type": "satellite",
        "status": "operational",
        "criticality": "high",
    }
    r = await client.post("/api/v1/assets", json=body, headers={**headers, "X-Workspace": "ws-a"})
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/assets", json={**body, "name": "SAT-B"}, headers={**headers, "X-Workspace": "ws-b"}
    )
    assert r.status_code == 201

    r = await client.get("/api/v1/assets", headers={**headers, "X-Workspace": "ws-a"})
    assert [a["name"] for a in r.json()["items"]] == ["SAT-A"]

    # No header -> unscoped legacy view sees both
    r = await client.get("/api/v1/assets", headers=headers)
    assert r.json()["total"] >= 2


async def test_unknown_workspace_404_generic(client, admin):
    _, headers = admin
    r = await client.get("/api/v1/assets", headers={**headers, "X-Workspace": "nope"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Workspace not found"


async def test_non_member_gets_same_404(client, admin, viewer):
    _, admin_headers = admin
    _, viewer_headers = viewer
    await _mk_ws(client, admin_headers, "private-ws")
    r = await client.get("/api/v1/assets", headers={**viewer_headers, "X-Workspace": "private-ws"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Workspace not found"  # same body as unknown slug


async def test_workspace_invite_redeem_creates_member(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "team-ws")
    r = await client.post(
        "/api/v1/workspaces/team-ws/invites",
        json={"email": "new.analyst@orbitalsentinel.space", "role": "analyst"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    assert token and r.json()["used_at"] is None

    r = await client.post(
        "/api/v1/invites/redeem",
        json={"token": token, "password": "correct horse battery", "full_name": "New Analyst"},
    )
    assert r.status_code == 201, r.text

    r = await client.get("/api/v1/workspaces/team-ws/members", headers=headers)
    assert "analyst" in {m["role"] for m in r.json()}

    # burned: second redemption fails with the generic message
    r = await client.post(
        "/api/v1/invites/redeem",
        json={"token": token, "password": "another password 123", "full_name": "X"},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "Invalid or expired invitation"


async def test_invite_bad_token_same_generic_error(client):
    r = await client.post(
        "/api/v1/invites/redeem",
        json={"token": "x" * 32, "password": "whatever whatever", "full_name": "X"},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "Invalid or expired invitation"


async def test_service_account_role_cap(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "svc-ws")
    r = await client.post(
        "/api/v1/workspaces/svc-ws/service-accounts",
        json={"name": "ingest bot", "email": "bot@orbitalsentinel.space", "role": "admin"},
        headers=headers,
    )
    assert r.status_code == 422
    assert "operator" in r.json()["detail"].lower()


async def test_api_key_lifecycle_and_auth(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "key-ws")
    r = await client.post(
        "/api/v1/workspaces/key-ws/service-accounts",
        json={"name": "ingest bot", "email": "bot2@orbitalsentinel.space", "role": "operator"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    account_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/workspaces/key-ws/service-accounts/{account_id}/keys",
        json={"name": "primary"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    raw, key_id = r.json()["key"], r.json()["id"]
    assert raw.startswith("aegis_sk_")

    # X-API-Key authenticates as the workspace-scoped service account
    r = await client.get("/api/v1/assets", headers={"X-API-Key": raw, "X-Workspace": "key-ws"})
    assert r.status_code == 200, r.text

    # wrong key -> generic 401
    r = await client.get("/api/v1/assets", headers={"X-API-Key": "aegis_sk_dead_beef"})
    assert r.status_code == 401

    # revoke -> key stops working
    r = await client.delete(
        f"/api/v1/workspaces/key-ws/service-accounts/keys/{key_id}", headers=headers
    )
    assert r.status_code == 204
    r = await client.get("/api/v1/assets", headers={"X-API-Key": raw})
    assert r.status_code == 401


async def test_list_service_accounts_returns_accounts_and_keys(client, admin):
    _, headers = admin
    await _mk_ws(client, headers, "list-ws")
    r = await client.post(
        "/api/v1/workspaces/list-ws/service-accounts",
        json={"name": "ingest bot", "email": "listbot@orbitalsentinel.space", "role": "operator"},
        headers=headers,
    )
    account_id = r.json()["id"]
    await client.post(
        f"/api/v1/workspaces/list-ws/service-accounts/{account_id}/keys",
        json={"name": "primary"},
        headers=headers,
    )

    r = await client.get("/api/v1/workspaces/list-ws/service-accounts", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == account_id
    assert body[0]["email"] == "listbot@orbitalsentinel.space"
    assert len(body[0]["keys"]) == 1
    assert body[0]["keys"][0]["name"] == "primary"
    # Raw key must never appear in the list response, only at mint time.
    assert "key" not in body[0]["keys"][0]


async def test_service_account_scoped_to_owning_workspace(client, admin):
    """A service account created under one workspace must not be mintable
    or revocable, nor listed, from a different workspace — even by a
    platform admin acting through that other workspace's admin path."""
    _, headers = admin
    await _mk_ws(client, headers, "ws-a")
    await _mk_ws(client, headers, "ws-b")

    r = await client.post(
        "/api/v1/workspaces/ws-a/service-accounts",
        json={"name": "a-bot", "email": "abot@orbitalsentinel.space", "role": "operator"},
        headers=headers,
    )
    account_id = r.json()["id"]

    # Minting a key for ws-a's account through ws-b's path must fail.
    r = await client.post(
        f"/api/v1/workspaces/ws-b/service-accounts/{account_id}/keys",
        json={"name": "cross-tenant"},
        headers=headers,
    )
    assert r.status_code == 404, r.text

    # It must still list correctly under its real workspace, and not the other.
    r = await client.get("/api/v1/workspaces/ws-a/service-accounts", headers=headers)
    assert [a["id"] for a in r.json()] == [account_id]
    r = await client.get("/api/v1/workspaces/ws-b/service-accounts", headers=headers)
    assert r.json() == []

    # Mint the key properly under its real workspace, then confirm revoking
    # it through the *other* workspace's path also fails.
    r = await client.post(
        f"/api/v1/workspaces/ws-a/service-accounts/{account_id}/keys",
        json={"name": "primary"},
        headers=headers,
    )
    key_id = r.json()["id"]
    r = await client.delete(
        f"/api/v1/workspaces/ws-b/service-accounts/keys/{key_id}", headers=headers
    )
    assert r.status_code == 404, r.text

    # ...but succeeds through the correct workspace.
    r = await client.delete(
        f"/api/v1/workspaces/ws-a/service-accounts/keys/{key_id}", headers=headers
    )
    assert r.status_code == 204


async def test_last_workspace_admin_guard(client, admin):
    me, headers = admin
    await _mk_ws(client, headers, "guard-ws")

    # Sole admin cannot demote themself
    r = await client.put(
        f"/api/v1/workspaces/guard-ws/members/{me.id}", json={"role": "viewer"}, headers=headers
    )
    assert r.status_code == 422

    # Nor be removed as last admin
    r = await client.delete(f"/api/v1/workspaces/guard-ws/members/{me.id}", headers=headers)
    assert r.status_code == 422


def test_new_roles_exist():
    assert Role("soc_manager") and Role("executive") and Role("auditor")
