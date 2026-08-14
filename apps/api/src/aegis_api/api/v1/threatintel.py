from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from aegis_api.api.deps import CurrentUser, SessionDep, require_roles
from aegis_api.models.enums import AlertSeverity, IndicatorType, Role
from aegis_api.models.user import User
from aegis_api.schemas.common import Page
from aegis_api.schemas.threatintel import (
    CorrelationResult,
    IndicatorCreate,
    IndicatorRead,
    IngestResult,
    ThreatIntelSummary,
    ThreatMatchRead,
)
from aegis_api.services.threatintel.engine import ThreatIntelService, match_to_read

router = APIRouter(prefix="/threat-intel", tags=["threat-intel"])

Analyst = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.ANALYST))]


@router.get("/summary", response_model=ThreatIntelSummary)
async def summary(session: SessionDep, _: CurrentUser) -> ThreatIntelSummary:
    return await ThreatIntelService(session).summary()


@router.get("/indicators", response_model=Page[IndicatorRead])
async def list_indicators(
    session: SessionDep,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    indicator_type: IndicatorType | None = None,
    severity: AlertSeverity | None = None,
    active: bool | None = None,
    search: str | None = None,
) -> Page[IndicatorRead]:
    items, total = await ThreatIntelService(session).list_indicators(
        limit=limit,
        offset=offset,
        indicator_type=indicator_type,
        severity=severity,
        active=active,
        search=search,
    )
    return Page(
        items=[IndicatorRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/indicators", response_model=IndicatorRead, status_code=status.HTTP_201_CREATED)
async def register_indicator(
    body: IndicatorCreate, session: SessionDep, actor: Analyst
) -> IndicatorRead:
    indicator = await ThreatIntelService(session).register(body, actor_id=actor.id)
    return IndicatorRead.model_validate(indicator)


@router.post("/ingest", response_model=list[IngestResult])
async def ingest(session: SessionDep, actor: Analyst) -> list[IngestResult]:
    return await ThreatIntelService(session).ingest(actor_id=actor.id)


@router.post("/correlate", response_model=CorrelationResult)
async def correlate(session: SessionDep, actor: Analyst) -> CorrelationResult:
    return await ThreatIntelService(session).correlate(actor_id=actor.id)


@router.get("/matches", response_model=list[ThreatMatchRead])
async def matches(session: SessionDep, _: CurrentUser) -> list[ThreatMatchRead]:
    return [match_to_read(m) for m in await ThreatIntelService(session).list_matches()]
