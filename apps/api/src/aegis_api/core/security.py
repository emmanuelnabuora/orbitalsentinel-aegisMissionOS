"""Security primitives: password hashing and access tokens.

Design decisions (see docs/adr/0002-security-baseline.md):
- Argon2id for password hashing (memory-hard, OWASP-recommended default).
- Short-lived HS256 JWTs for Phase 0; asymmetric keys + refresh rotation
  arrive with the auth service in Phase 1.
- Tokens carry `sub`, `roles`, `iss`, `iat`, `exp`, `jti` — nothing sensitive.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from aegis_api.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults (tuned per OWASP)


class TokenError(Exception):
    """Raised when a token is invalid, expired, or malformed."""


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str, roles: list[str] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "purpose": "access",
        "roles": roles or [],
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],  # explicit allow-list: no alg confusion
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "purpose"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("purpose") != "access":
        raise TokenError("Wrong token purpose")
    return payload


def create_mfa_token(subject: str) -> str:
    """Short-lived token proving password success, pending second factor.

    Carries purpose='mfa' and grants no API access: decode_access_token
    enforces purpose='access', so this token is only consumable by
    decode_mfa_token.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "purpose": "mfa",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_mfa_token(token: str) -> str:
    """Return the subject of a valid MFA challenge token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "purpose", "iss", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired MFA token") from exc
    if payload.get("purpose") != "mfa":
        raise TokenError("Invalid or expired MFA token")
    return payload["sub"]
