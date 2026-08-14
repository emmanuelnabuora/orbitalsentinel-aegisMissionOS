import uuid

from fastapi import APIRouter

from aegis_api.api.deps import CurrentUser, SessionDep
from aegis_api.schemas.sentinel import ChatRequest, ChatResponse, IncidentAnalysis
from aegis_api.services.sentinel.engine import SentinelService

router = APIRouter(prefix="/sentinel", tags=["sentinel"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, session: SessionDep, user: CurrentUser) -> ChatResponse:
    return await SentinelService(session).chat(body.message, actor_id=user.id)


@router.post("/incidents/{incident_id}/analyze", response_model=IncidentAnalysis)
async def analyze_incident(
    incident_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> IncidentAnalysis:
    return await SentinelService(session).analyze_incident(incident_id, actor_id=user.id)


from pydantic import BaseModel as _BaseModel

from aegis_api.services.sentinel.providers import get_provider as _get_provider


class SentinelStatus(_BaseModel):
    provider: str
    live: bool
    model: str | None = None


@router.get("/status", response_model=SentinelStatus)
async def sentinel_status(_: CurrentUser) -> SentinelStatus:
    p = _get_provider()
    model = getattr(p, "model", None)
    if hasattr(p, "aclose"):
        await p.aclose()
    return SentinelStatus(provider=p.name, live=p.live, model=model)
