"""SSO via OpenID Connect (authorization code + PKCE).

Provider-agnostic: anything exposing standard OIDC discovery works
(Okta, Entra ID, Keycloak, login.gov). Flow state (state, nonce, PKCE
verifier) lives in Redis with a 10-minute TTL — the API stays stateless.

ID tokens are validated properly: signature against the provider's JWKS,
issuer, audience, expiry, and nonce. `http_transport` is injectable so the
whole flow is testable against an in-process stub IdP.
"""

import base64
import hashlib
import json
import secrets
import uuid
from urllib.parse import urlencode

import httpx
import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.config import get_settings
from aegis_api.core.exceptions import AuthError
from aegis_api.core.security import create_access_token
from aegis_api.models.enums import Role
from aegis_api.models.user import User, UserRoleAssignment
from aegis_api.repositories.users import UserRepository
from aegis_api.services.audit import AuditService
from aegis_api.services.auth import AuthService

_STATE_TTL_SECONDS = 600


def sso_configured() -> bool:
    s = get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_client_secret and s.oidc_redirect_url)


class SSOService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.session = session
        self.redis = redis
        self.users = UserRepository(session)
        self.audit = AuditService(session)
        self.auth = AuthService(session)
        self._transport = http_transport
        self.settings = get_settings()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=15, transport=self._transport)

    async def _discovery(self) -> dict:
        url = f"{self.settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
        async with self._client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def begin(self) -> str:
        """Create flow state and return the provider authorization URL."""
        if not sso_configured():
            raise AuthError("SSO is not configured")
        discovery = await self._discovery()

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        flow_state = json.dumps({"nonce": nonce, "verifier": verifier})
        await self.redis.setex(f"sso:state:{state}", _STATE_TTL_SECONDS, flow_state)

        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.oidc_client_id,
                "redirect_uri": self.settings.oidc_redirect_url,
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{discovery['authorization_endpoint']}?{query}"

    async def complete(self, code: str, state: str) -> tuple[str, str, User]:
        """Exchange the code, validate the ID token, map/provision the user."""
        raw = await self.redis.getdel(f"sso:state:{state}")
        if raw is None:
            raise AuthError("Invalid or expired SSO state")
        flow = json.loads(raw)

        discovery = await self._discovery()
        async with self._client() as client:
            token_resp = await client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.settings.oidc_redirect_url,
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                    "code_verifier": flow["verifier"],
                },
            )
            if token_resp.status_code != 200:
                raise AuthError("SSO token exchange failed")
            id_token = token_resp.json().get("id_token")
            if not id_token:
                raise AuthError("Provider returned no ID token")

            jwks_resp = await client.get(discovery["jwks_uri"])
            jwks_resp.raise_for_status()
            jwks = jwks_resp.json()

        claims = self._validate_id_token(id_token, jwks)
        if claims.get("nonce") != flow["nonce"]:
            raise AuthError("SSO nonce mismatch")

        email = claims.get("email")
        if not email:
            raise AuthError("Provider did not supply an email claim")

        user = await self.users.get_by_email(email.lower())
        if user is None:
            if not self.settings.oidc_auto_provision:
                self.audit.record(actor_id=None, action="sso.unknown_user", detail={"email": email})
                await self.session.commit()
                raise AuthError("No AEGIS account for this identity")
            user = User(
                email=email.lower(),
                full_name=claims.get("name") or email,
                # SSO users have no local password; random unusable hash.
                password_hash=f"sso:{secrets.token_hex(16)}",
                is_active=True,
            )
            self.session.add(user)
            await self.session.flush()
            self.session.add(UserRoleAssignment(user_id=user.id, role=Role.VIEWER))
            await self.session.flush()
            self.audit.record(
                actor_id=user.id,
                action="sso.user_provisioned",
                resource_type="user",
                resource_id=user.id,
            )
            # session.get() returns the identity-map instance, so selectin
            # never fires for the just-created user; refresh explicitly.
            await self.session.refresh(user, attribute_names=["role_assignments"])
        if not user.is_active:
            raise AuthError("Account is deactivated")

        refresh_plain = self.auth._issue_refresh(user.id, family_id=uuid.uuid4())
        await self.session.flush()
        roles = [r.value for r in user.roles]
        access = create_access_token(str(user.id), roles=roles)
        self.audit.record(
            actor_id=user.id, action="auth.login_sso", resource_type="user", resource_id=user.id
        )
        await self.session.commit()
        return access, refresh_plain, user

    def _validate_id_token(self, id_token: str, jwks: dict) -> dict:
        try:
            kid = jwt.get_unverified_header(id_token).get("kid")
            key_data = next(k for k in jwks["keys"] if k.get("kid") == kid)
            key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
            return jwt.decode(
                id_token,
                key=key,
                algorithms=["RS256"],  # allow-list, as everywhere
                audience=self.settings.oidc_client_id,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except StopIteration as exc:
            raise AuthError("No matching signing key in provider JWKS") from exc
        except jwt.PyJWTError as exc:
            raise AuthError("ID token validation failed") from exc
