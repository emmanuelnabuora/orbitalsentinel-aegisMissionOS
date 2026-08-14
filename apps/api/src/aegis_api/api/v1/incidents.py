import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, Query, status

from aegis_api.core.abac import can_read, visible_markings
from aegis_api.api.deps import WorkspaceDep, CurrentUser, SessionDep, require_roles
from aegis_api.models.enums import IncidentStatus, Role
from aegis_api.models.user import User
from aegis_api.schemas.common import Page
from aegis_api.schemas.incident import (
    IncidentCreate,
    IncidentDetail,
    IncidentNote,
    IncidentRead,
    IncidentUpdate,
)
from aegis_api.services.alerts import to_read as alert_to_read
from aegis_api.services.incidents import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])

Responder = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.ANALYST))]


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreate, session: SessionDep, actor: Responder, ws: WorkspaceDep) -> IncidentRead:
    incident = await IncidentService(session).create(body, actor_id=actor.id, workspace_id=ws.id if ws else None)
    return IncidentRead.model_validate(incident)


@router.get("", response_model=Page[IncidentRead])
async def list_incidents(
    session: SessionDep,
    ws: WorkspaceDep,
    viewer: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    incident_status: Annotated[IncidentStatus | None, Query(alias="status")] = None,
) -> Page[IncidentRead]:
    incidents, total = await IncidentService(session).repo.list(
        limit=limit,
        workspace_id=ws.id if ws else None,
        allowed_markings=visible_markings(viewer.clearance), offset=offset, status=incident_status
    )
    return Page(
        items=[IncidentRead.model_validate(i) for i in incidents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID, session: SessionDep, viewer: CurrentUser
) -> IncidentDetail:
    svc = IncidentService(session)
    incident = await svc.get(incident_id)
    if not can_read(viewer, incident):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    linked, _total = await svc.alerts.list(limit=100, offset=0, incident_id=incident.id)
    detail = IncidentDetail.model_validate(
        {
            **IncidentRead.model_validate(incident).model_dump(),
            "events": incident.events,
            "alerts": [],
        }
    )
    detail.alerts = [alert_to_read(a) for a in linked]
    return detail


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: uuid.UUID, body: IncidentUpdate, session: SessionDep, actor: Responder
) -> IncidentRead:
    incident = await IncidentService(session).update(incident_id, body, actor_id=actor.id)
    return IncidentRead.model_validate(incident)


@router.post("/{incident_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(
    incident_id: uuid.UUID, body: IncidentNote, session: SessionDep, actor: Responder
) -> dict:
    await IncidentService(session).add_note(incident_id, body.message, actor_id=actor.id)
    return {"status": "created"}
