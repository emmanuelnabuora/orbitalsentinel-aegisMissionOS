"""Fine-grained permissions (Phase 13).

Roles are bundles of permissions. Authorization checks name the
*permission*, not the role, so future custom roles are a data problem
(map role -> permission set), not a code change. Platform ADMIN holds
every permission implicitly.

Least privilege: a role gets exactly the permissions its workspace
persona needs (docs/phase-13-rbac-spec.md holds the full matrix).
"""

from enum import StrEnum

from aegis_api.models.enums import Role


class Permission(StrEnum):
    # assets & missions
    ASSETS_READ = "assets:read"
    ASSETS_WRITE = "assets:write"
    MISSIONS_READ = "missions:read"
    MISSIONS_WRITE = "missions:write"
    # detections
    ALERTS_READ = "alerts:read"
    ALERTS_TRIAGE = "alerts:triage"
    INCIDENTS_READ = "incidents:read"
    INCIDENTS_MANAGE = "incidents:manage"
    INCIDENTS_RESPOND = "incidents:respond"   # containment / response actions
    THREATINTEL_READ = "threatintel:read"
    THREATINTEL_MANAGE = "threatintel:manage"
    # analysis & reporting
    SENTINEL_USE = "sentinel:use"
    TWIN_SIMULATE = "twin:simulate"
    REPORTS_READ = "reports:read"
    REPORTS_GENERATE = "reports:generate"
    QUANTUM_READ = "quantum:read"
    # governance
    AUDIT_READ = "audit:read"
    USERS_MANAGE = "users:manage"
    WORKSPACE_MANAGE = "workspace:manage"
    KEYS_MANAGE = "keys:manage"


_VIEW = {
    Permission.ASSETS_READ, Permission.MISSIONS_READ, Permission.ALERTS_READ,
    Permission.INCIDENTS_READ, Permission.REPORTS_READ,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),  # everything
    Role.OPERATOR: frozenset(_VIEW | {
        Permission.ASSETS_WRITE, Permission.MISSIONS_WRITE,
        Permission.ALERTS_TRIAGE, Permission.TWIN_SIMULATE,
        Permission.QUANTUM_READ, Permission.SENTINEL_USE,
    }),
    Role.ANALYST: frozenset(_VIEW | {
        Permission.ALERTS_TRIAGE, Permission.THREATINTEL_READ,
        Permission.THREATINTEL_MANAGE, Permission.SENTINEL_USE,
        Permission.QUANTUM_READ,
    }),
    Role.SOC_MANAGER: frozenset(_VIEW | {
        Permission.ALERTS_TRIAGE, Permission.INCIDENTS_MANAGE,
        Permission.THREATINTEL_READ, Permission.REPORTS_GENERATE,
        Permission.SENTINEL_USE,
    }),
    Role.INCIDENT_RESPONDER: frozenset(_VIEW | {
        Permission.ALERTS_TRIAGE, Permission.INCIDENTS_MANAGE,
        Permission.INCIDENTS_RESPOND, Permission.SENTINEL_USE,
    }),
    Role.EXECUTIVE: frozenset({
        Permission.MISSIONS_READ, Permission.REPORTS_READ,
        Permission.INCIDENTS_READ,
    }),
    Role.AUDITOR: frozenset({
        Permission.AUDIT_READ, Permission.REPORTS_READ,
    }),
    Role.VIEWER: frozenset(_VIEW),
}


# Building blocks for the custom-role builder (Phase 14). Groups are
# code-defined; custom roles composed from them are stored in the DB.
PERMISSION_GROUPS: dict[str, frozenset[Permission]] = {
    "fleet-read": frozenset({Permission.ASSETS_READ, Permission.MISSIONS_READ}),
    "fleet-manage": frozenset({Permission.ASSETS_WRITE, Permission.MISSIONS_WRITE}),
    "detections-read": frozenset({Permission.ALERTS_READ, Permission.INCIDENTS_READ}),
    "detections-triage": frozenset({Permission.ALERTS_TRIAGE, Permission.INCIDENTS_MANAGE}),
    "response-actions": frozenset({Permission.INCIDENTS_RESPOND}),
    "threat-intel": frozenset({Permission.THREATINTEL_READ, Permission.THREATINTEL_MANAGE}),
    "analysis-tools": frozenset({Permission.SENTINEL_USE, Permission.TWIN_SIMULATE, Permission.QUANTUM_READ}),
    "reporting": frozenset({Permission.REPORTS_READ, Permission.REPORTS_GENERATE}),
    "governance": frozenset({Permission.AUDIT_READ}),
    "org-administration": frozenset({Permission.USERS_MANAGE, Permission.WORKSPACE_MANAGE, Permission.KEYS_MANAGE}),
}

# Grants that require a second workspace admin's approval when included
# in a custom role (separation of duties, ADR-0014).
SENSITIVE_PERMISSIONS: frozenset[Permission] = frozenset({
    Permission.INCIDENTS_RESPOND,
    Permission.AUDIT_READ,
    Permission.USERS_MANAGE,
    Permission.WORKSPACE_MANAGE,
    Permission.KEYS_MANAGE,
})


def resolve_groups(group_names: list[str]) -> frozenset[Permission]:
    out: set[Permission] = set()
    for name in group_names:
        if name not in PERMISSION_GROUPS:
            raise KeyError(name)
        out |= PERMISSION_GROUPS[name]
    return frozenset(out)


def permissions_for(roles: list[Role]) -> frozenset[Permission]:
    out: set[Permission] = set()
    for r in roles:
        out |= ROLE_PERMISSIONS.get(r, frozenset())
    return frozenset(out)


def has_permission(roles: list[Role], perm: Permission) -> bool:
    return perm in permissions_for(roles)
