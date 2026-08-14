"""Celestrak SOCRATES conjunction client.

SOCRATES publishes satellite close-approach predictions (updated a few
times daily). We consume the CSV export; the path is configurable
because CelesTrak has moved/renamed exports before. Columns are matched
case-insensitively against the documented SOCRATES field names.

No authentication.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from aegis_api.core.logging import get_logger
from aegis_api.services.ingestion.clients.base import BaseSourceClient
from aegis_api.services.ingestion.schemas import ConjunctionRecord

log = get_logger("aegis.ingestion")

CELESTRAK_BASE = "https://celestrak.org"
DEFAULT_SOCRATES_PATH = "/SOCRATES/socrates.csv"

_ALIASES = {
    "norad_cat_id_1": {"norad_cat_id_1", "sat1_norad", "noradid1"},
    "object_name_1": {"object_name_1", "sat1_name", "name1"},
    "norad_cat_id_2": {"norad_cat_id_2", "sat2_norad", "noradid2"},
    "object_name_2": {"object_name_2", "sat2_name", "name2"},
    "tca": {"tca", "tca_time"},
    "min_range_km": {"tca_range", "min_range", "min_rng_km", "range_km"},
    "relative_speed_km_s": {"tca_relative_speed", "rel_speed", "relative_speed_km_s"},
    "max_probability": {"max_prob", "max_probability", "collision_probability"},
}


def _index(header: list[str]) -> dict[str, int] | None:
    norm = [h.strip().lower() for h in header]
    out: dict[str, int] = {}
    for field, names in _ALIASES.items():
        idx = next((i for i, h in enumerate(norm) if h in names), None)
        if idx is None:
            return None
        out[field] = idx
    return out


def _parse_tca(raw: str) -> datetime:
    cleaned = raw.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class SocratesClient(BaseSourceClient):
    def __init__(self, path: str = DEFAULT_SOCRATES_PATH, **kwargs) -> None:
        super().__init__(base_url=CELESTRAK_BASE, **kwargs)
        self._path = path

    async def get_conjunctions(self) -> list[ConjunctionRecord]:
        resp = await self._client.get(self._path)
        resp.raise_for_status()
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        if not rows:
            return []
        idx = _index(rows[0])
        if idx is None:
            log.warning("socrates_header_unrecognized", header=rows[0][:8])
            return []
        out: list[ConjunctionRecord] = []
        for row in rows[1:]:
            if len(row) <= max(idx.values()):
                continue
            try:
                out.append(
                    ConjunctionRecord(
                        norad_cat_id_1=int(row[idx["norad_cat_id_1"]]),
                        object_name_1=row[idx["object_name_1"]].strip(),
                        norad_cat_id_2=int(row[idx["norad_cat_id_2"]]),
                        object_name_2=row[idx["object_name_2"]].strip(),
                        tca=_parse_tca(row[idx["tca"]]),
                        min_range_km=float(row[idx["min_range_km"]]),
                        relative_speed_km_s=float(row[idx["relative_speed_km_s"]]),
                        max_probability=float(row[idx["max_probability"]]),
                    )
                )
            except (ValueError, KeyError):
                continue  # malformed row; skip, keep the feed alive
        return out
