"""Phase 17 — ABAC: clearance dominance and classification markings."""

from __future__ import annotations

from aegis_api.core.abac import Classification, dominates, visible_markings
from aegis_api.models.enums import Role


def test_dominance_ordering():
    assert dominates("secret", "cui") and dominates("cui", "unclassified")
    assert not dominates("unclassified", "cui")
    assert dominates("cui", "cui")


def test_visible_markings():
    assert visible_markings("unclassified") == ["unclassified"]
    assert set(visible_markings("secret")) == {"unclassified", "cui", "secret"}


async def _mk_asset(client, headers, name, classification="unclassified"):
    r = await client.post(
        "/api/v1/assets",
        json={
            "name": name, "asset_type": "satellite", "status": "operational",
            "criticality": "high", "classification": classification,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_classified_assets_filtered_from_lists(client, admin, make_user):
    _, admin_headers = admin
    await _mk_asset(client, admin_headers, "PUBLIC-SAT")
    secret = await _mk_asset(client, admin_headers, "SECRET-SAT", "secret")

    _, viewer_headers = await make_user("lowclear@orbitalsentinel.io", Role.VIEWER)

    names = [a["name"] for a in (await client.get("/api/v1/assets", headers=viewer_headers)).json()["items"]]
    assert "PUBLIC-SAT" in names and "SECRET-SAT" not in names

    # detail read: 404, not 403 — existence must not leak
    r = await client.get(f"/api/v1/assets/{secret['id']}", headers=viewer_headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Asset not found"


async def test_clearance_grant_reveals(client, admin, make_user):
    _, admin_headers = admin
    secret = await _mk_asset(client, admin_headers, "SECRET-SAT-2", "secret")
    analyst, analyst_headers = await make_user("clearme@orbitalsentinel.io", Role.ANALYST)

    r = await client.get(f"/api/v1/assets/{secret['id']}", headers=analyst_headers)
    assert r.status_code == 404

    r = await client.put(
        f"/api/v1/users/{analyst.id}/clearance",
        json={"clearance": "secret"},
        headers=admin_headers,
    )
    assert r.status_code == 200 and r.json()["clearance"] == "secret"

    r = await client.get(f"/api/v1/assets/{secret['id']}", headers=analyst_headers)
    assert r.status_code == 200
    assert r.json()["classification"] == "secret"
    names = [a["name"] for a in (await client.get("/api/v1/assets", headers=analyst_headers)).json()["items"]]
    assert "SECRET-SAT-2" in names


async def test_cui_alert_visibility(client, admin, make_user):
    _, admin_headers = admin
    r = await client.post(
        "/api/v1/alerts",
        json={"title": "CUI anomaly", "severity": "high", "classification": "cui"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    alert_id = r.json()["id"]

    _, low_headers = await make_user("lowalert@orbitalsentinel.io", Role.ANALYST)
    titles = [a["title"] for a in (await client.get("/api/v1/alerts", headers=low_headers)).json()["items"]]
    assert "CUI anomaly" not in titles
    assert (await client.get(f"/api/v1/alerts/{alert_id}", headers=low_headers)).status_code == 404

    # admin (default clearance unclassified) — admins are NOT exempt from
    # clearance: need-to-know applies to everyone.
    assert (await client.get(f"/api/v1/alerts/{alert_id}", headers=admin_headers)).status_code == 404


async def test_admin_needs_clearance_too(client, admin):
    me, headers = admin
    secret = await _mk_asset(client, headers, "NEEDTOKNOW", "secret")
    r = await client.get(f"/api/v1/assets/{secret['id']}", headers=headers)
    assert r.status_code == 404  # created it, still can't read it without clearance

    await client.put(f"/api/v1/users/{me.id}/clearance", json={"clearance": "secret"}, headers=headers)
    r = await client.get(f"/api/v1/assets/{secret['id']}", headers=headers)
    assert r.status_code == 200


async def test_invalid_clearance_rejected(client, admin):
    me, headers = admin
    r = await client.put(
        f"/api/v1/users/{me.id}/clearance", json={"clearance": "cosmic"}, headers=headers
    )
    assert r.status_code == 422
