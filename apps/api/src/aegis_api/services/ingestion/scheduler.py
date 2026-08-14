"""IngestionScheduler — asyncio polling loops on per-source cadences.

Runs inside the API process (modular monolith, ADR-0001) as background
tasks started from the FastAPI lifespan when settings.data_source ==
"live". Cadences respect upstream guidance: GP element sets change a
few times per day; SWPC products update every 1-5 minutes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aegis_api.core.logging import get_logger
from aegis_api.services.ingestion.service import IngestionService

log = get_logger("aegis.ingestion")


@dataclass
class IngestionCadences:
    kp_seconds: int = 300              # 5 min
    solar_wind_seconds: int = 120      # 2 min
    bulletins_seconds: int = 300       # 5 min
    catalog_seconds: int = 6 * 3600    # 6 h
    conjunction_seconds: int = 8 * 3600  # 8 h (SOCRATES updates ~3x/day)
    cdm_seconds: int = 4 * 3600        # 4 h (Space-Track; respects throttling guidance)
    catalog_group: str = "active"


@dataclass
class IngestionScheduler:
    service: IngestionService
    cadences: IngestionCadences = field(default_factory=IngestionCadences)
    _tasks: list[asyncio.Task] = field(default_factory=list)

    async def _loop(
        self, name: str, interval_s: int, fn: Callable[[], Awaitable[object]]
    ) -> None:
        # Small initial jitter avoids a thundering herd on process start.
        await asyncio.sleep(min(5, interval_s))
        while True:
            try:
                await fn()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - fail-open, keep looping
                log.exception("ingestion_loop_error", loop=name)
            await asyncio.sleep(interval_s)

    def start(self) -> None:
        c = self.cadences
        specs: list[tuple[str, int, Callable[[], Awaitable[object]]]] = [
            ("kp", c.kp_seconds, self.service.poll_kp),
            ("solar_wind", c.solar_wind_seconds, self.service.poll_solar_wind),
            ("bulletins", c.bulletins_seconds, self.service.poll_swpc_bulletins),
            (
                "catalog",
                c.catalog_seconds,
                lambda: self.service.refresh_catalog(c.catalog_group),
            ),
            ("conjunctions", c.conjunction_seconds, self.service.poll_conjunctions),
            ("cdms", c.cdm_seconds, self.service.poll_cdms),
        ]
        for name, interval, fn in specs:
            self._tasks.append(
                asyncio.create_task(self._loop(name, interval, fn), name=f"ingest:{name}")
            )
        log.info("ingestion_scheduler_started", loops=len(self._tasks))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        log.info("ingestion_scheduler_stopped")
