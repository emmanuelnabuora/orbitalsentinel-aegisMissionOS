from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from aegis_api.api.deps import CurrentUser, SessionDep
from aegis_api.core.config import get_settings
from aegis_api.core.ratelimit import FixedWindowLimiter, get_login_limiter
from aegis_api.core.security import create_mfa_token
from aegis_api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MFAActivateRequest,
    MFAActivateResponse,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshRequest,
    TokenResponse,
)
from aegis_api.schemas.user import UserRead
from aegis_api.services.auth import AuthService
from aegis_api.services.mfa import MFAService

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(access: str, refresh: str) -> TokenResponse:
    ttl = get_settings().access_token_ttl_minutes * 60
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=ttl)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: SessionDep,
    limiter: Annotated[FixedWindowLimiter, Depends(get_login_limiter)],
) -> LoginResponse:
    # Two budgets: per source IP and per target account. Either can trip.
    client_ip = request.client.host if request.client else "unknown"
    await limiter.enforce(f"ip:{client_ip}", f"email:{body.email.lower()}")
    access, refresh, user = await AuthService(session).login(body.email, body.password)
    if access is None:
        return LoginResponse(mfa_required=True, mfa_token=create_mfa_token(str(user.id)))
    ttl = get_settings().access_token_ttl_minutes * 60
    return LoginResponse(access_token=access, refresh_token=refresh, expires_in=ttl)


@router.post("/mfa/verify", response_model=TokenResponse)
async def mfa_verify(
    body: MFAVerifyRequest,
    request: Request,
    session: SessionDep,
    limiter: Annotated[FixedWindowLimiter, Depends(get_login_limiter)],
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    await limiter.enforce(f"ip:{client_ip}")
    access, refresh, _ = await AuthService(session).complete_mfa_login(body.mfa_token, body.code)
    return _token_response(access, refresh)


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(session: SessionDep, user: CurrentUser) -> MFASetupResponse:
    secret, uri, svg = await MFAService(session).start_setup(user)
    return MFASetupResponse(secret=secret, otpauth_uri=uri, qr_svg=svg)


@router.post("/mfa/activate", response_model=MFAActivateResponse)
async def mfa_activate(
    body: MFAActivateRequest, session: SessionDep, user: CurrentUser
) -> MFAActivateResponse:
    codes = await MFAService(session).activate(user, body.code)
    return MFAActivateResponse(recovery_codes=codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_disable(body: MFADisableRequest, session: SessionDep, user: CurrentUser) -> None:
    await MFAService(session).disable(user, body.code)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: SessionDep) -> TokenResponse:
    access, new_refresh = await AuthService(session).refresh(body.refresh_token)
    return _token_response(access, new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, session: SessionDep) -> None:
    await AuthService(session).logout(body.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
