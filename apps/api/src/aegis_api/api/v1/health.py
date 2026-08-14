"""Liveness and readiness endpoints.

/healthz  - process is alive (no dependencies touched)
/readyz   - dependencies reachable (Postgres, Redis) - degrades honestly
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from aegis_api.core.config import get_settings

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    version: str
    env: str


class Readiness(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/healthz", response_model=Health)
async def healthz() -> Health:
    s = get_settings()
    return Health(status="ok", version=s.version, env=s.env)


@router.get("/readyz", response_model=Readiness)
async def readyz(response: Response) -> Readiness:
    checks: dict[str, str] = {}

    # Postgres
    try:
        from sqlalchemy import text

        from aegis_api.core.db import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:  # noqa: BLE001 - readiness must never raise
        checks["postgres"] = "unreachable"

    # Redis
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(get_settings().redis_url)
        try:
            await client.ping()
            checks["redis"] = "ok"
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001
        checks["redis"] = "unreachable"

    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="ready" if ready else "degraded", checks=checks)
