"""Seed the OrbitalSentinel workspace with the founding team and one demo
user per role-workspace persona.

Usage:
    python scripts/seed_team.py            # random passwords, printed once
    python scripts/seed_team.py --demo     # fixed demo passwords (LOCAL/DEMO ONLY)

Idempotent: existing users/workspaces are left untouched. In random
mode, passwords are printed ONCE — store them in a password manager.
--demo uses the documented fixed passwords below and must never be
used against a production database.
"""

import asyncio
import secrets
import sys

DEMO_MODE = "--demo" in sys.argv


def _demo_password(email: str) -> str:
    """Fixed, documented demo passwords: OrbSent!2026.<local-part>"""
    return f"OrbSent!2026.{email.split('@')[0]}"

import sqlalchemy as sa

sys.path.insert(0, "src")

from aegis_api.core.db import get_engine, get_session_factory  # noqa: E402
from aegis_api.core.security import hash_password  # noqa: E402
from aegis_api.models import Base  # noqa: E402
from aegis_api.models.enums import Role  # noqa: E402
from aegis_api.models.user import User, UserRoleAssignment  # noqa: E402
from aegis_api.models.workspace import Workspace, WorkspaceMembership  # noqa: E402

WORKSPACE = ("OrbitalSentinel", "orbitalsentinel")

# (email, full_name, platform_roles, workspace_role)
TEAM = [
    ("e.nakitare@orbitalsentinel.space", "Emmanuel Nakitare", [Role.ADMIN], Role.ADMIN),
    ("n.kigen@orbitalsentinel.space", "Nelson Kigen", [Role.ADMIN], Role.ADMIN),
    ("h.mudenyo@orbitalsentinel.space", "Haggai Mudenyo", [], Role.OPERATOR),
    ("l.kiplagat@orbitalsentinel.space", "Laban Kiplagat", [], Role.OPERATOR),
]

# One demo account per role-workspace persona (workspace-scoped roles).
PERSONAS = [
    ("demo.orgadmin@orbitalsentinel.space", "Demo Org Admin", Role.ADMIN),
    ("demo.operator@orbitalsentinel.space", "Demo Mission Operator", Role.OPERATOR),
    ("demo.analyst@orbitalsentinel.space", "Demo Security Analyst", Role.ANALYST),
    ("demo.socmanager@orbitalsentinel.space", "Demo SOC Manager", Role.SOC_MANAGER),
    ("demo.responder@orbitalsentinel.space", "Demo Incident Responder", Role.INCIDENT_RESPONDER),
    ("demo.executive@orbitalsentinel.space", "Demo Executive", Role.EXECUTIVE),
    ("demo.auditor@orbitalsentinel.space", "Demo Auditor", Role.AUDITOR),
]


async def main() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # no-op if migrated

    factory = get_session_factory()
    creds: list[tuple[str, str]] = []

    async with factory() as session:
        ws = (
            await session.execute(
                sa.select(Workspace).where(Workspace.slug == WORKSPACE[1])
            )
        ).scalar_one_or_none()
        if ws is None:
            ws = Workspace(name=WORKSPACE[0], slug=WORKSPACE[1])
            session.add(ws)
            await session.flush()
            print(f"created workspace: {ws.slug}")

        async def ensure_user(email, name, platform_roles, ws_role):
            user = (
                await session.execute(sa.select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is None:
                password = _demo_password(email) if DEMO_MODE else secrets.token_urlsafe(16)
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    full_name=name,
                    role_assignments=[UserRoleAssignment(role=r) for r in platform_roles],
                )
                session.add(user)
                await session.flush()
                creds.append((email, password))
            membership = await session.get(WorkspaceMembership, (ws.id, user.id))
            if membership is None:
                session.add(
                    WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=ws_role)
                )

        for email, name, proles, wsrole in TEAM:
            await ensure_user(email, name, proles, wsrole)
        for email, name, wsrole in PERSONAS:
            await ensure_user(email, name, [], wsrole)

        await session.commit()

    if creds and DEMO_MODE:
        print("\n=== DEMO credentials (fixed — local/demo use only) ===")
        for email, password in creds:
            print(f"  {email}  {password}")
    elif creds:
        print("\n=== Generated credentials (shown once) ===")
        for email, password in creds:
            print(f"  {email}  {password}")
    else:
        print("all users already present; nothing generated")


if __name__ == "__main__":
    asyncio.run(main())
