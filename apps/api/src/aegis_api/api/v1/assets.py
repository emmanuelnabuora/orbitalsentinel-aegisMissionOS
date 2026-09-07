import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aegis_api.api.deps import CurrentUser, SessionDep, WorkspaceDep, require_roles
from aegis_api.core.abac import can_read, visible_markings
from aegis_api.models.enums import AssetStatus, AssetType, Criticality, Role
from aegis_api.models.user import User
from aegis_api.schemas.asset import AssetCreate, AssetDependencyCreate, AssetRead, AssetUpdate
from aegis_api.schemas.common import Page
from aegis_api.services.assets import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])

Operator = Annotated[User, Depends(require_roles(Role.OPERATOR))]
Admin = Annotated[User, Depends(require_roles())]


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    body: AssetCreate, session: SessionDep, actor: Operator, ws: WorkspaceDep
) -> AssetRead:
    asset = await AssetService(session).create(
        body, actor_id=actor.id, workspace_id=ws.id if ws else None
    )
    return AssetRead.model_validate(asset)


@router.get("", response_model=Page[AssetRead])
async def list_assets(
    session: SessionDep,
    ws: WorkspaceDep,
    viewer: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    asset_type: AssetType | None = None,
    asset_status: Annotated[AssetStatus | None, Query(alias="status")] = None,
    criticality: Criticality | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[AssetRead]:
    assets, total = await AssetService(session).repo.list(
        limit=limit,
        workspace_id=ws.id if ws else None,
        allowed_markings=visible_markings(viewer.clearance),
        offset=offset,
        asset_type=asset_type,
        status=asset_status,
        criticality=criticality,
        search=search,
    )
    return Page(
        items=[AssetRead.model_validate(a) for a in assets], total=total, limit=limit, offset=offset
    )


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(asset_id: uuid.UUID, session: SessionDep, viewer: CurrentUser) -> AssetRead:
    asset = await AssetService(session).get(asset_id)
    if not can_read(viewer, asset):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return AssetRead.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetRead)
async def update_asset(
    asset_id: uuid.UUID, body: AssetUpdate, session: SessionDep, actor: Operator
) -> AssetRead:
    asset = await AssetService(session).update(asset_id, body, actor_id=actor.id)
    return AssetRead.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(asset_id: uuid.UUID, session: SessionDep, actor: Admin) -> None:
    await AssetService(session).delete(asset_id, actor_id=actor.id)


@router.post("/{asset_id}/dependencies", status_code=status.HTTP_201_CREATED)
async def add_dependency(
    asset_id: uuid.UUID, body: AssetDependencyCreate, session: SessionDep, actor: Operator
) -> dict:
    await AssetService(session).add_dependency(asset_id, body, actor_id=actor.id)
    return {"status": "created"}
