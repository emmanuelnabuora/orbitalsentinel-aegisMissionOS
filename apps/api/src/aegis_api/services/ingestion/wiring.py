"""App-factory glue: build the scheduler when data_source == "live"."""

from __future__ import annotations

from aegis_api.core.config import Settings
from aegis_api.core.db import get_session_factory
from aegis_api.services.ingestion.clients.celestrak import CelestrakClient
from aegis_api.services.ingestion.clients.socrates import SocratesClient
from aegis_api.services.ingestion.clients.swpc import SwpcClient
from aegis_api.services.ingestion.scheduler import IngestionCadences, IngestionScheduler
from aegis_api.services.ingestion.service import IngestionService
from aegis_api.services.ingestion.sinks import (
    DbAlertSink,
    DbEphemerisSink,
    DbIncidentSink,
    DbTrackedAssetLookup,
)


def build_scheduler(settings: Settings) -> IngestionScheduler | None:
    if settings.data_source != "live":
        return None
    factory = get_session_factory()
    service = IngestionService(
        swpc=SwpcClient(),
        celestrak=CelestrakClient(),
        alert_sink=DbAlertSink(factory),
        ephemeris_sink=DbEphemerisSink(factory),
        socrates=SocratesClient(),
        tracked_lookup=DbTrackedAssetLookup(factory),
        incident_sink=DbIncidentSink(factory),
    )
    cadences = IngestionCadences(catalog_group=settings.ingest_catalog_group)
    return IngestionScheduler(service=service, cadences=cadences)
