import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from aegis_api.api.deps import CurrentUser, SessionDep, require_roles
from aegis_api.models.enums import Role
from aegis_api.models.user import User
from aegis_api.schemas.digitaltwin import (
    ScenarioCreate,
    ScenarioRead,
    ScenarioSimulate,
    SimulationResult,
)
from aegis_api.services.digitaltwin import DigitalTwinService

router = APIRouter(prefix="/digital-twin", tags=["digital-twin"])

Analyst = Annotated[User, Depends(require_roles(Role.OPERATOR, Role.ANALYST))]


@router.post("/simulate", response_model=SimulationResult)
async def simulate(body: ScenarioSimulate, session: SessionDep, actor: Analyst) -> SimulationResult:
    return await DigitalTwinService(session).simulate(body, actor_id=actor.id)


@router.get("/scenarios", response_model=list[ScenarioRead])
async def list_scenarios(session: SessionDep, _: CurrentUser) -> list[ScenarioRead]:
    scenarios = await DigitalTwinService(session).list_scenarios()
    return [ScenarioRead.model_validate(s) for s in scenarios]


@router.post("/scenarios", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    body: ScenarioCreate, session: SessionDep, actor: Analyst
) -> ScenarioRead:
    scenario = await DigitalTwinService(session).create_scenario(body, actor_id=actor.id)
    return ScenarioRead.model_validate(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
async def get_scenario(scenario_id: uuid.UUID, session: SessionDep, _: CurrentUser) -> ScenarioRead:
    scenario = await DigitalTwinService(session).get_scenario(scenario_id)
    return ScenarioRead.model_validate(scenario)


@router.post("/scenarios/{scenario_id}/run", response_model=SimulationResult)
async def run_scenario(
    scenario_id: uuid.UUID, session: SessionDep, actor: Analyst
) -> SimulationResult:
    return await DigitalTwinService(session).run_scenario(scenario_id, actor_id=actor.id)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: uuid.UUID, session: SessionDep, actor: Analyst) -> None:
    await DigitalTwinService(session).delete_scenario(scenario_id, actor_id=actor.id)
