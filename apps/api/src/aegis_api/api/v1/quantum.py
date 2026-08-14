import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from aegis_api.api.deps import CurrentUser, SessionDep, require_roles
from aegis_api.models.crypto import CryptoRecord
from aegis_api.models.enums import Role
from aegis_api.models.user import User
from aegis_api.schemas.common import Page
from aegis_api.schemas.quantum import CryptoRecordCreate, CryptoRecordRead, QuantumReadiness
from aegis_api.services.quantum import QuantumService

router = APIRouter(prefix="/quantum", tags=["quantum"])

Operator = Annotated[User, Depends(require_roles(Role.OPERATOR))]


def _to_read(r: CryptoRecord) -> CryptoRecordRead:
    data = CryptoRecordRead.model_validate(r)
    data.asset_name = r.asset.name if r.asset else None
    return data


@router.post("/inventory", response_model=CryptoRecordRead, status_code=status.HTTP_201_CREATED)
async def register_record(
    body: CryptoRecordCreate, session: SessionDep, actor: Operator
) -> CryptoRecordRead:
    return _to_read(await QuantumService(session).register(body, actor_id=actor.id))


@router.get("/inventory", response_model=Page[CryptoRecordRead])
async def list_inventory(
    session: SessionDep,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    asset_id: uuid.UUID | None = None,
) -> Page[CryptoRecordRead]:
    records, total = await QuantumService(session).repo.list(
        limit=limit, offset=offset, asset_id=asset_id
    )
    return Page(items=[_to_read(r) for r in records], total=total, limit=limit, offset=offset)


@router.get("/readiness", response_model=QuantumReadiness)
async def readiness(session: SessionDep, _: CurrentUser) -> QuantumReadiness:
    return await QuantumService(session).readiness()
