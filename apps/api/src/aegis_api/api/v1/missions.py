import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aegis_api.api.deps import CurrentUser, SessionDep, WorkspaceDep, require_roles
from aegis_api.core.abac import can_read, visible_markings
from aegis_api.models.enums import MissionStatus, Role
from aegis_api.models.user import User
from aegis_api.schemas.common import Page
from aegis_api.schemas.mission import (
    MissionAssetAttach,
    MissionAssetRead,
    MissionCreate,
    MissionGraph,
    MissionRead,
    MissionUpdate,
)
from aegis_api.services.missions import MissionService

router = APIRouter(prefix="/missions", tags=["missions"])

Operator = Annotated[User, Depends(require_roles(Role.OPERATOR))]
Admin = Annotated[User, Depends(require_roles())]


@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission(
    body: MissionCreate, session: SessionDep, actor: Operator, ws: WorkspaceDep
) -> MissionRead:
    mission = await MissionService(session).create(
        body, actor_id=actor.id, workspace_id=ws.id if ws else None
    )
    return MissionRead.model_validate(mission)


@router.get("", response_model=Page[MissionRead])
async def list_missions(
    session: SessionDep,
    ws: WorkspaceDep,
    viewer: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    mission_status: Annotated[MissionStatus | None, Query(alias="status")] = None,
) -> Page[MissionRead]:
    missions, total = await MissionService(session).repo.list(
        limit=limit,
        workspace_id=ws.id if ws else None,
        allowed_markings=visible_markings(viewer.clearance),
        offset=offset,
        status=mission_status,
    )
    return Page(
        items=[MissionRead.model_validate(m) for m in missions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission(
    mission_id: uuid.UUID, session: SessionDep, viewer: CurrentUser
) -> MissionRead:
    mission = await MissionService(session).get(mission_id)
    if not can_read(viewer, mission):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return MissionRead.model_validate(mission)


@router.patch("/{mission_id}", response_model=MissionRead)
async def update_mission(
    mission_id: uuid.UUID, body: MissionUpdate, session: SessionDep, actor: Operator
) -> MissionRead:
    mission = await MissionService(session).update(mission_id, body, actor_id=actor.id)
    return MissionRead.model_validate(mission)


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mission(mission_id: uuid.UUID, session: SessionDep, actor: Admin) -> None:
    await MissionService(session).delete(mission_id, actor_id=actor.id)


@router.get("/{mission_id}/assets", response_model=list[MissionAssetRead])
async def list_mission_assets(
    mission_id: uuid.UUID, session: SessionDep, _: CurrentUser
) -> list[MissionAssetRead]:
    mission = await MissionService(session).get(mission_id)
    return [
        MissionAssetRead(asset=link.asset, dependency_criticality=link.dependency_criticality)
        for link in mission.asset_links
    ]


@router.post("/{mission_id}/assets", status_code=status.HTTP_201_CREATED)
async def attach_asset(
    mission_id: uuid.UUID, body: MissionAssetAttach, session: SessionDep, actor: Operator
) -> dict:
    await MissionService(session).attach_asset(mission_id, body, actor_id=actor.id)
    return {"status": "attached"}


@router.delete("/{mission_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_asset(
    mission_id: uuid.UUID, asset_id: uuid.UUID, session: SessionDep, actor: Operator
) -> None:
    await MissionService(session).detach_asset(mission_id, asset_id, actor_id=actor.id)


@router.get("/{mission_id}/graph", response_model=MissionGraph)
async def mission_graph(
    mission_id: uuid.UUID, session: SessionDep, viewer: CurrentUser
) -> MissionGraph:
    mission = await MissionService(session).get(mission_id)
    if not can_read(viewer, mission):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return await MissionService(session).graph(mission_id)
