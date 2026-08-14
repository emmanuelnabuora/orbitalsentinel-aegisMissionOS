import uuid

from fastapi import APIRouter

from aegis_api.api.deps import CurrentUser, SessionDep
from aegis_api.schemas.missioniq import FleetSummary, MissionAssurance
from aegis_api.services.missioniq import MissionIQService

router = APIRouter(prefix="/missioniq", tags=["missioniq"])


@router.get("/summary", response_model=FleetSummary)
async def fleet_summary(session: SessionDep, _: CurrentUser) -> FleetSummary:
    return await MissionIQService(session).fleet()


@router.get("/missions/{mission_id}", response_model=MissionAssurance)
async def mission_assurance(
    mission_id: uuid.UUID, session: SessionDep, _: CurrentUser
) -> MissionAssurance:
    return await MissionIQService(session).assurance(mission_id)
