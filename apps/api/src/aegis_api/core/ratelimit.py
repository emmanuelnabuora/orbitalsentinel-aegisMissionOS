"""Redis-backed fixed-window rate limiting.

Fail-open by design: if Redis is unreachable, requests pass and a warning is
logged. For login brute-force protection, availability of the control plane
must not become a denial-of-service vector against operators (ADR-0004).
"""

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from aegis_api.core.config import get_settings
from aegis_api.core.exceptions import RateLimitedError

logger = structlog.get_logger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


class FixedWindowLimiter:
    def __init__(self, redis: Redis, *, prefix: str, limit: int, window_seconds: int):
        self.redis = redis
        self.prefix = prefix
        self.limit = limit
        self.window = window_seconds

    async def enforce(self, *keys: str) -> None:
        """Raise RateLimitedError if any key exceeded its window budget."""
        try:
            for key in keys:
                full = f"rl:{self.prefix}:{key}"
                count = await self.redis.incr(full)
                if count == 1:
                    await self.redis.expire(full, self.window)
                if count > self.limit:
                    logger.warning("rate_limited", prefix=self.prefix, key=key)
                    raise RateLimitedError("Too many attempts. Wait a few minutes and try again.")
        except RedisError:
            logger.warning("rate_limit_backend_unavailable", prefix=self.prefix)


def get_login_limiter() -> FixedWindowLimiter:
    s = get_settings()
    return FixedWindowLimiter(
        get_redis(),
        prefix="login",
        limit=s.login_rate_limit,
        window_seconds=s.login_rate_window_seconds,
    )
