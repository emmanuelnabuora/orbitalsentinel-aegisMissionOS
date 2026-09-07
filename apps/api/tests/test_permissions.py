"""Phase 13 — fine-grained permission layer."""

from aegis_api.core.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
    permissions_for,
)
from aegis_api.models.enums import Role


def test_admin_holds_every_permission():
    assert ROLE_PERMISSIONS[Role.ADMIN] == frozenset(Permission)


def test_every_role_has_a_permission_set():
    for role in Role:
        assert role in ROLE_PERMISSIONS, f"no permission set for {role}"


def test_least_privilege_examples():
    # Auditors read audit + reports, nothing operational
    assert has_permission([Role.AUDITOR], Permission.AUDIT_READ)
    assert not has_permission([Role.AUDITOR], Permission.ASSETS_WRITE)
    assert not has_permission([Role.AUDITOR], Permission.INCIDENTS_RESPOND)

    # Executives are read-only
    assert has_permission([Role.EXECUTIVE], Permission.REPORTS_READ)
    assert not has_permission([Role.EXECUTIVE], Permission.REPORTS_GENERATE)

    # Only responders (and admin) hold response actions
    holders = [r for r in Role if Permission.INCIDENTS_RESPOND in ROLE_PERMISSIONS[r]]
    assert set(holders) == {Role.ADMIN, Role.INCIDENT_RESPONDER}


def test_multi_role_union():
    perms = permissions_for([Role.AUDITOR, Role.ANALYST])
    assert Permission.AUDIT_READ in perms
    assert Permission.THREATINTEL_READ in perms


async def test_audit_endpoint_permission_gate(client, admin, make_user):
    _, admin_headers = admin
    _, responder_headers = await make_user("resp@orbitalsentinel.io", Role.INCIDENT_RESPONDER)
    _, auditor_headers = await make_user("aud@orbitalsentinel.io", Role.AUDITOR)

    r = await client.get("/api/v1/audit", headers=auditor_headers)
    assert r.status_code == 200

    r = await client.get("/api/v1/audit", headers=admin_headers)
    assert r.status_code == 200  # admin passes via implicit full grant

    r = await client.get("/api/v1/audit", headers=responder_headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "Permission denied"
