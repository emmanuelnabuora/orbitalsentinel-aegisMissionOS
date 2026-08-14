"""SSO: full OIDC code+PKCE flow against a stub identity provider.

The stub IdP lives in an httpx.MockTransport: discovery, token, and JWKS
endpoints, signing real RS256 ID tokens with a generated RSA key. This proves
signature/issuer/audience/nonce validation and user mapping end to end,
hermetically.
"""

from urllib.parse import parse_qs, urlparse

import fakeredis.aioredis
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from aegis_api.core.config import get_settings
from aegis_api.core.exceptions import AuthError
from aegis_api.services.sso import SSOService

ISSUER = "https://idp.orbitalsentinel.test"
CLIENT_ID = "aegis-missionos"


@pytest.fixture
def oidc_env(monkeypatch):
    monkeypatch.setenv("AEGIS_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("AEGIS_OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("AEGIS_OIDC_CLIENT_SECRET", "stub-secret")
    monkeypatch.setenv("AEGIS_OIDC_REDIRECT_URL", "https://aegis.test/sso/callback")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class StubIdP:
    """Minimal OIDC provider: discovery + token + JWKS, RS256-signed."""

    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "stub-key-1"
        self.subject = "idp-user-42"
        self.email = "analyst@orbitalsentinel.io"
        self.name = "Ada Analyst"
        self.nonce: str | None = None  # captured from the auth URL by the test

    def _jwks(self) -> dict:
        pub = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        return {"keys": [{**pub, "kid": self.kid, "use": "sig", "alg": "RS256"}]}

    def _id_token(self) -> str:
        import time

        now = int(time.time())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": CLIENT_ID,
                "sub": self.subject,
                "email": self.email,
                "name": self.name,
                "nonce": self.nonce,
                "iat": now,
                "exp": now + 300,
            },
            self.key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/.well-known/openid-configuration":
                return httpx.Response(
                    200,
                    json={
                        "issuer": ISSUER,
                        "authorization_endpoint": f"{ISSUER}/authorize",
                        "token_endpoint": f"{ISSUER}/token",
                        "jwks_uri": f"{ISSUER}/jwks",
                    },
                )
            if path == "/token":
                body = parse_qs(request.content.decode())
                # a real IdP verifies these; the stub asserts they arrive
                assert body["grant_type"] == ["authorization_code"]
                assert body["client_secret"] == ["stub-secret"]
                assert body["code_verifier"][0]
                if body["code"] != ["good-code"]:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                return httpx.Response(200, json={"id_token": self._id_token()})
            if path == "/jwks":
                return httpx.Response(200, json=self._jwks())
            return httpx.Response(404)

        return httpx.MockTransport(handler)


@pytest.fixture
def idp():
    return StubIdP()


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


async def _begin(svc: SSOService, idp: StubIdP) -> str:
    url = await svc.begin()
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"]
    assert q["client_id"] == [CLIENT_ID]
    idp.nonce = q["nonce"][0]
    return q["state"][0]


async def test_sso_flow_provisions_and_logs_in(db, oidc_env, idp, redis, monkeypatch):
    monkeypatch.setenv("AEGIS_OIDC_AUTO_PROVISION", "true")
    get_settings.cache_clear()
    async with db() as session:
        svc = SSOService(session, redis, http_transport=idp.transport())
        state = await _begin(svc, idp)
        access, refresh, user = await svc.complete("good-code", state)

    assert user.email == "analyst@orbitalsentinel.io"
    assert [r.value for r in user.roles] == ["viewer"]  # least privilege on provision
    assert access and refresh

    payload = jwt.get_unverified_header(access)
    assert payload["alg"] == "HS256"  # our token, not the IdP's


async def test_sso_state_is_single_use_and_required(db, oidc_env, idp, redis, monkeypatch):
    monkeypatch.setenv("AEGIS_OIDC_AUTO_PROVISION", "true")
    get_settings.cache_clear()
    async with db() as session:
        svc = SSOService(session, redis, http_transport=idp.transport())
        state = await _begin(svc, idp)
        await svc.complete("good-code", state)
        with pytest.raises(AuthError):  # replay
            await svc.complete("good-code", state)
        with pytest.raises(AuthError):  # forged state
            await svc.complete("good-code", "not-a-real-state")


async def test_sso_unknown_user_rejected_without_auto_provision(db, oidc_env, idp, redis):
    # AEGIS_OIDC_AUTO_PROVISION defaults to false
    async with db() as session:
        svc = SSOService(session, redis, http_transport=idp.transport())
        state = await _begin(svc, idp)
        with pytest.raises(AuthError, match="No AEGIS account"):
            await svc.complete("good-code", state)


async def test_sso_rejects_wrong_issuer_signature(db, oidc_env, idp, redis, monkeypatch):
    monkeypatch.setenv("AEGIS_OIDC_AUTO_PROVISION", "true")
    get_settings.cache_clear()
    evil = StubIdP()  # different RSA key, same claims shape

    def swap_jwks(request: httpx.Request) -> httpx.Response:
        # legit discovery/token, but JWKS serves a non-matching key set
        if request.url.path == "/jwks":
            jwks = evil._jwks()
            jwks["keys"][0]["kid"] = idp.kid  # same kid, wrong key material
            return httpx.Response(200, json=jwks)
        return idp.transport().handler(request)

    async with db() as session:
        svc = SSOService(session, redis, http_transport=httpx.MockTransport(swap_jwks))
        state = await _begin(svc, idp)
        with pytest.raises(AuthError, match="ID token validation failed"):
            await svc.complete("good-code", state)
