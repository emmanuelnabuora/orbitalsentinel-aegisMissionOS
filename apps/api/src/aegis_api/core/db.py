"""Async database engine and session dependency.

Engine is created lazily so the app can boot (and tests can run)
without a live database. Repositories receive AsyncSession via DI —
no module ever imports the engine directly.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from aegis_api.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models (Phase 1 onward)."""


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, always closed."""
    get_engine()
    assert _session_factory is not None  # noqa: S101 - invariant, set by get_engine
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory for background workers (ingestion scheduler)."""
    get_engine()
    assert _session_factory is not None  # noqa: S101 - invariant, set by get_engine
    return _session_factory
