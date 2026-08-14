"""MFA: TOTP enrollment, challenge login, recovery codes, purpose isolation."""

import pyotp
import pytest
from tests.conftest import PASSWORD  # single source of truth

from aegis_api.core.security import (
    TokenError,
    create_mfa_token,
    decode_access_token,
    decode_mfa_token,
)


async def _enroll(client, headers) -> tuple[str, list[str]]:
    """Run setup + activate; return (secret, recovery_codes)."""
    setup = (await client.post("/api/v1/auth/mfa/setup", headers=headers)).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert "<svg" in setup["qr_svg"]
    code = pyotp.TOTP(setup["secret"]).now()
    resp = await client.post("/api/v1/auth/mfa/activate", json={"code": code}, headers=headers)
    assert resp.status_code == 200
    codes = resp.json()["recovery_codes"]
    assert len(codes) == 10
    return setup["secret"], codes


async def test_mfa_enrollment_and_challenge_login(client, operator):
    user, headers = operator
    secret, _ = await _enroll(client, headers)

    # /auth/me reflects enrollment
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["mfa_enabled"] is True

    # password login now returns a challenge, not tokens
    login = (
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    ).json()
    assert login["mfa_required"] is True
    assert login["access_token"] is None
    assert login["mfa_token"]

    # wrong code rejected
    bad = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": login["mfa_token"], "code": "000000"}
    )
    assert bad.status_code == 401

    # correct TOTP completes login with full tokens
    good = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": login["mfa_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert good.status_code == 200
    body = good.json()
    assert body["access_token"] and body["refresh_token"]
    assert decode_access_token(body["access_token"])["sub"] == str(user.id)


async def test_recovery_code_works_once(client, operator):
    user, headers = operator
    _, codes = await _enroll(client, headers)

    login = (
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    ).json()
    ok = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": login["mfa_token"], "code": codes[0]}
    )
    assert ok.status_code == 200

    # same recovery code is consumed
    login2 = (
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    ).json()
    replay = await client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": login2["mfa_token"], "code": codes[0]}
    )
    assert replay.status_code == 401


async def test_mfa_disable_requires_valid_factor(client, operator):
    user, headers = operator
    secret, _ = await _enroll(client, headers)

    assert (
        await client.post("/api/v1/auth/mfa/disable", json={"code": "000000"}, headers=headers)
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/mfa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=headers
        )
    ).status_code == 204

    # password login is single-factor again
    login = (
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    ).json()
    assert login["mfa_required"] is False
    assert login["access_token"]


async def test_mfa_token_grants_no_api_access(client, operator):
    user, _ = operator
    challenge = create_mfa_token(str(user.id))
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {challenge}"})
    assert resp.status_code == 401
    # and access tokens are not valid MFA tokens
    with pytest.raises(TokenError):
        decode_mfa_token(await _login_token(client, user))


async def _login_token(client, user) -> str:
    body = (
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    ).json()
    return body["access_token"]
