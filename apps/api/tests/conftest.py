import os

# Deterministic test environment before any app import
os.environ.setdefault("AEGIS_ENV", "test")
os.environ.setdefault("AEGIS_SECRET_KEY", "test-secret-key-0123456789abcdef0123456789abcdef")

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import aegis_api.models  # noqa: F401 - register ORM metadata
from aegis_api.core.db import Base, get_session
from aegis_api.core.ratelimit import FixedWindowLimiter, get_login_limiter
from aegis_api.core.security import create_access_token
from aegis_api.main import create_app
from aegis_api.models.enums import Role
from aegis_api.services.users import UserService

PASSWORD = "correct horse battery staple"


@pytest.fixture
async def db():
    """Test database with the full schema.

    Default: in-memory SQLite (fast, hermetic). Set TEST_DATABASE_URL to a
    PostgreSQL URL to run the identical suite against the real dialect —
    CI does this so dialect drift is caught before deploy.
    """
    url = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")
    if url.startswith("sqlite"):
        engine = create_async_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    else:
        engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    if not url.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def app(db):
    application = create_app()

    async def _override():
        async with db() as session:
            yield session

    application.dependency_overrides[get_session] = _override

    class _NoopLimiter(FixedWindowLimiter):
        def __init__(self):
            pass

        async def enforce(self, *keys: str) -> None:
            return None

    # Rate limiting has its own dedicated tests (test_rate_limit.py, fakeredis);
    # the general suite must not depend on a live Redis.
    application.dependency_overrides[get_login_limiter] = _NoopLimiter
    return application


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def make_user(db):
    """Factory: create a user with the given roles, return (user, bearer headers)."""

    async def _make(email: str, *roles: Role):
        async with db() as session:
            user = await UserService(session).create(
                email=email,
                password=PASSWORD,
                full_name="Test User",
                roles=list(roles),
                actor_id=None,
            )
        token = create_access_token(str(user.id), roles=[r.value for r in roles])
        return user, {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
async def admin(make_user):
    return await make_user("admin@orbitalsentinel.io", Role.ADMIN)


@pytest.fixture
async def operator(make_user):
    return await make_user("operator@orbitalsentinel.io", Role.OPERATOR)


@pytest.fixture
async def viewer(make_user):
    return await make_user("viewer@orbitalsentinel.io", Role.VIEWER)


SAT = {
    "name": "SENTRY-7",
    "asset_type": "satellite",
    "criticality": "critical",
    "status": "operational",
    "attributes": {"orbit": "LEO", "norad_id": "99901"},
}
GROUND = {
    "name": "Vandenberg Ground Station",
    "asset_type": "ground_station",
    "criticality": "high",
    "status": "operational",
}


async def create_asset(client, headers, payload=None):
    resp = await client.post("/api/v1/assets", json=payload or SAT, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()
