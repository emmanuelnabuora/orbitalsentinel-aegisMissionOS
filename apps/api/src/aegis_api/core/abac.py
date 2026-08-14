"""Attribute-Based Access Control (Phase 17).

Two shipped attribute predicates:

1. **Clearance dominance.** Resources carry a classification marking
   (UNCLASSIFIED < CUI < SECRET); users carry a clearance. A user sees
   a resource only if their clearance dominates its marking. Lists
   filter silently; detail reads answer 404 — never 403 — so the
   existence of classified resources does not leak.
2. **Ownership.** `is_owner_or_admin` for owner-gated mutations.

Defaults preserve behavior: everything is UNCLASSIFIED and every user's
clearance starts at UNCLASSIFIED, so dominance always holds until
markings are applied (expand-then-contract, ADR-0005).
"""

from __future__ import annotations

import uuid
from enum import StrEnum


class Classification(StrEnum):
    UNCLASSIFIED = "unclassified"
    CUI = "cui"
    SECRET = "secret"


_ORDER: dict[Classification, int] = {
    Classification.UNCLASSIFIED: 0,
    Classification.CUI: 1,
    Classification.SECRET: 2,
}


def dominates(clearance: Classification | str, marking: Classification | str) -> bool:
    return _ORDER[Classification(clearance)] >= _ORDER[Classification(marking)]


def visible_markings(clearance: Classification | str) -> list[str]:
    """Marking values a holder of `clearance` may see (for SQL IN filters)."""
    level = _ORDER[Classification(clearance)]
    return [c.value for c in Classification if _ORDER[c] <= level]


def can_read(user, resource) -> bool:
    """Clearance predicate over a user and any marked resource."""
    marking = getattr(resource, "classification", Classification.UNCLASSIFIED)
    clearance = getattr(user, "clearance", Classification.UNCLASSIFIED)
    return dominates(clearance, marking)


def is_owner_or_admin(user, resource, *, owner_attr: str = "owner_id") -> bool:
    from aegis_api.models.enums import Role

    if Role.ADMIN in set(user.roles):
        return True
    owner: uuid.UUID | None = getattr(resource, owner_attr, None)
    return owner is not None and owner == user.id
