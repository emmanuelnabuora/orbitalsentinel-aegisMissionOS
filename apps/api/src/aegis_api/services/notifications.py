"""Notification emission and preferences (Phase 15).

Fan-out is synchronous and small (workspace admins / single recipient);
mutes are honored at emission time via WorkspacePreference.data
["muted_kinds"]. Fail-open: notification errors never fail the calling
operation — callers already committed their own state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.logging import get_logger
from aegis_api.models.enums import Role
from aegis_api.models.notification import Notification, WorkspacePreference
from aegis_api.models.workspace import WorkspaceMembership

log = get_logger("aegis.notifications")


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _muted(self, user_id: uuid.UUID, workspace_id: uuid.UUID | None, kind: str) -> bool:
        if workspace_id is None:
            return False
        pref = await self.session.get(WorkspacePreference, (user_id, workspace_id))
        if pref is None:
            return False
        return kind in (pref.data or {}).get("muted_kinds", [])

    async def notify(
        self,
        *,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str = "",
        workspace_id: uuid.UUID | None = None,
        link: str | None = None,
    ) -> Notification | None:
        if await self._muted(user_id, workspace_id, kind):
            return None
        n = Notification(
            user_id=user_id,
            workspace_id=workspace_id,
            kind=kind,
            title=title,
            body=body,
            link=link,
        )
        self.session.add(n)
        return n

    async def notify_workspace_admins(
        self,
        *,
        workspace_id: uuid.UUID,
        kind: str,
        title: str,
        body: str = "",
        link: str | None = None,
        exclude_user_id: uuid.UUID | None = None,
    ) -> int:
        stmt = sa.select(WorkspaceMembership.user_id).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role == Role.ADMIN,
        )
        admin_ids = [row[0] for row in (await self.session.execute(stmt)).all()]
        count = 0
        for uid in admin_ids:
            if exclude_user_id is not None and uid == exclude_user_id:
                continue
            if (
                await self.notify(
                    user_id=uid,
                    kind=kind,
                    title=title,
                    body=body,
                    workspace_id=workspace_id,
                    link=link,
                )
                is not None
            ):
                count += 1
        return count

    # -- inbox --------------------------------------------------------------

    async def list_for(self, user_id: uuid.UUID, *, limit: int = 30) -> list[Notification]:
        stmt = (
            sa.select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def unread_count(self, user_id: uuid.UUID) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
        n = await self.session.get(Notification, notification_id)
        if n is None or n.user_id != user_id or n.read_at is not None:
            return False
        n.read_at = datetime.now(UTC)
        await self.session.commit()
        return True

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        stmt = (
            sa.update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0


class PreferenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> dict:
        pref = await self.session.get(WorkspacePreference, (user_id, workspace_id))
        return pref.data if pref else {}

    async def put(self, user_id: uuid.UUID, workspace_id: uuid.UUID, data: dict) -> dict:
        pref = await self.session.get(WorkspacePreference, (user_id, workspace_id))
        if pref is None:
            pref = WorkspacePreference(user_id=user_id, workspace_id=workspace_id, data=data)
            self.session.add(pref)
        else:
            pref.data = data
        await self.session.commit()
        return pref.data
