"""Notification inbox and per-workspace preferences (Phase 15)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from aegis_api.api.deps import CurrentUser, SessionDep, WorkspaceDep
from aegis_api.schemas.notification import NotificationInbox, NotificationRead, PreferenceDoc
from aegis_api.services.notifications import NotificationService, PreferenceService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationInbox)
async def inbox(
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> NotificationInbox:
    svc = NotificationService(session)
    items = await svc.list_for(user.id, limit=limit)
    unread = await svc.unread_count(user.id)
    return NotificationInbox(
        unread=unread, items=[NotificationRead.model_validate(n) for n in items]
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    if not await NotificationService(session).mark_read(user.id, notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(session: SessionDep, user: CurrentUser) -> None:
    await NotificationService(session).mark_all_read(user.id)


prefs_router = APIRouter(prefix="/preferences", tags=["preferences"])


@prefs_router.get("", response_model=PreferenceDoc)
async def get_preferences(
    session: SessionDep, user: CurrentUser, ws: WorkspaceDep
) -> PreferenceDoc:
    if ws is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select a workspace first")
    return PreferenceDoc(data=await PreferenceService(session).get(user.id, ws.id))


@prefs_router.put("", response_model=PreferenceDoc)
async def put_preferences(
    body: PreferenceDoc, session: SessionDep, user: CurrentUser, ws: WorkspaceDep
) -> PreferenceDoc:
    if ws is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select a workspace first")
    data = await PreferenceService(session).put(user.id, ws.id, body.data)
    return PreferenceDoc(data=data)
