"""Login brute-force protection (Redis fixed-window)."""

import fakeredis.aioredis
import pytest

from aegis_api.core.exceptions import RateLimitedError
from aegis_api.core.ratelimit import FixedWindowLimiter, get_login_limiter


@pytest.fixture
def limiter():
    return FixedWindowLimiter(
        fakeredis.aioredis.FakeRedis(decode_responses=True),
        prefix="login",
        limit=3,
        window_seconds=60,
    )


async def test_allows_up_to_limit_then_blocks(limiter):
    for _ in range(3):
        await limiter.enforce("ip:10.0.0.1")
    with pytest.raises(RateLimitedError):
        await limiter.enforce("ip:10.0.0.1")


async def test_budgets_are_independent_per_key(limiter):
    for _ in range(3):
        await limiter.enforce("ip:10.0.0.1")
    await limiter.enforce("ip:10.0.0.2")  # different source unaffected


async def test_login_endpoint_returns_429_when_tripped(app, client, operator):
    strict = FixedWindowLimiter(
        fakeredis.aioredis.FakeRedis(decode_responses=True),
        prefix="login",
        limit=2,
        window_seconds=60,
    )
    app.dependency_overrides[get_login_limiter] = lambda: strict

    creds = {"email": "nobody@orbitalsentinel.io", "password": "WrongPassword123"}
    codes = [(await client.post("/api/v1/auth/login", json=creds)).status_code for _ in range(4)]
    assert codes[:2] == [401, 401]
    assert codes[2] == 429
    assert codes[3] == 429
