"""Celestrak GP (General Perturbations) catalog client.

Endpoint: https://celestrak.org/NORAD/elements/gp.php — no auth, OMM JSON.
Element sets change at most a few times per day; the scheduler polls on a
multi-hour cadence to stay a good citizen.
"""

from __future__ import annotations

from aegis_api.services.ingestion.clients.base import BaseSourceClient
from aegis_api.services.ingestion.schemas import GPRecord

CELESTRAK_BASE = "https://celestrak.org"
GP_PATH = "/NORAD/elements/gp.php"


class CelestrakClient(BaseSourceClient):
    def __init__(self, **kwargs) -> None:
        super().__init__(base_url=CELESTRAK_BASE, **kwargs)

    async def get_group(self, group: str = "active") -> list[GPRecord]:
        data = await self._get_json(GP_PATH, params={"GROUP": group, "FORMAT": "json"})
        return self._parse(data)

    async def get_by_catnr(self, norad_cat_id: int) -> GPRecord | None:
        data = await self._get_json(
            GP_PATH, params={"CATNR": str(norad_cat_id), "FORMAT": "json"}
        )
        records = self._parse(data)
        return records[0] if records else None

    async def get_by_name(self, name: str) -> list[GPRecord]:
        data = await self._get_json(GP_PATH, params={"NAME": name, "FORMAT": "json"})
        return self._parse(data)

    @staticmethod
    def _parse(data: object) -> list[GPRecord]:
        if not isinstance(data, list):
            # Celestrak returns a plain string like "No GP data found" on miss.
            return []
        return [GPRecord.model_validate(row) for row in data]
