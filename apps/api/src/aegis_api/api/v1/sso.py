from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis

from aegis_api.api.deps import SessionDep
from aegis_api.core.ratelimit import get_redis
from aegis_api.schemas.auth import TokenResponse
from aegis_api.services.sso import SSOService, sso_configured

router = APIRouter(prefix="/auth/sso", tags=["auth"])

RedisDep = Annotated[Redis, Depends(get_redis)]


class SSOStatus(BaseModel):
    configured: bool


class SSOBeginResponse(BaseModel):
    authorization_url: str


class SSOCallbackRequest(BaseModel):
    code: str
    state: str


@router.get("/status", response_model=SSOStatus)
async def status() -> SSOStatus:
    return SSOStatus(configured=sso_configured())


@router.get("/begin", response_model=SSOBeginResponse)
async def begin(session: SessionDep, redis: RedisDep) -> SSOBeginResponse:
    url = await SSOService(session, redis).begin()
    return SSOBeginResponse(authorization_url=url)


@router.post("/callback", response_model=TokenResponse)
async def callback(body: SSOCallbackRequest, session: SessionDep, redis: RedisDep) -> TokenResponse:
    access, refresh, _ = await SSOService(session, redis).complete(body.code, body.state)
    from aegis_api.api.v1.auth import _token_response

    return _token_response(access, refresh)
