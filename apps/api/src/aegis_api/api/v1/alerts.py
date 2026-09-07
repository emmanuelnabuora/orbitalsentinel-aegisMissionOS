import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aegis_api.api.deps import CurrentUser, SessionDep, WorkspaceDep, require_roles
from aegis_api.core.abac import can_read, visible_markings
from aegis_api.models.enums import AlertSeverity, AlertStatus, Role
from aegis_api.models.user import User
from aegis_api.schemas.alert import AlertCreate, AlertRead, AlertUpdate
from aegis_api.schemas.common import Page
from aegis_api.services.alerts import AlertService, to_read

router = APIRouter(prefix="/alerts", tags=["alerts"])

Operator = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.ANALYST))]


@router.post("", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AlertCreate, session: SessionDep, actor: Operator, ws: WorkspaceDep
) -> AlertRead:
    return to_read(
        await AlertService(session).create(
            body, actor_id=actor.id, workspace_id=ws.id if ws else None
        )
    )


@router.get("", response_model=Page[AlertRead])
async def list_alerts(
    session: SessionDep,
    ws: WorkspaceDep,
    viewer: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    severity: AlertSeverity | None = None,
    alert_status: Annotated[AlertStatus | None, Query(alias="status")] = None,
    asset_id: uuid.UUID | None = None,
) -> Page[AlertRead]:
    alerts, total = await AlertService(session).repo.list(
        limit=limit,
        workspace_id=ws.id if ws else None,
        allowed_markings=visible_markings(viewer.clearance),
        offset=offset,
        severity=severity,
        status=alert_status,
        asset_id=asset_id,
    )
    return Page(items=[to_read(a) for a in alerts], total=total, limit=limit, offset=offset)


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(alert_id: uuid.UUID, session: SessionDep, viewer: CurrentUser) -> AlertRead:
    alert = await AlertService(session).get(alert_id)
    if not can_read(viewer, alert):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return to_read(alert)


@router.patch("/{alert_id}", response_model=AlertRead)
async def update_alert(
    alert_id: uuid.UUID, body: AlertUpdate, session: SessionDep, actor: Operator
) -> AlertRead:
    return to_read(await AlertService(session).update(alert_id, body, actor_id=actor.id))
