"""Live data ingestion (Phase 11): Celestrak GP catalog + NOAA SWPC.

Pulls real orbital and space-weather data and maps it into alerts and
asset ephemeris. Gated by settings.data_source ("seed" | "live").
Fail-open: source outages never degrade the platform (ADR-0011).
"""

from aegis_api.services.ingestion.scheduler import IngestionScheduler
from aegis_api.services.ingestion.service import IngestionService

__all__ = ["IngestionScheduler", "IngestionService"]
