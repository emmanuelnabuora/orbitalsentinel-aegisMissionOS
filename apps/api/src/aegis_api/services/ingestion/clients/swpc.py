"""NOAA Space Weather Prediction Center client.

Base: https://services.swpc.noaa.gov — free JSON, no authentication.

  /json/planetary_k_index_1m.json             -> 1-minute estimated Kp
  /products/summary/solar-wind-speed.json     -> latest solar wind speed
  /products/summary/solar-wind-mag-field.json -> latest IMF Bt/Bz
  /products/alerts.json                       -> issued bulletins
"""

from __future__ import annotations

from datetime import datetime, timezone

from aegis_api.services.ingestion.clients.base import BaseSourceClient
from aegis_api.services.ingestion.schemas import KpReading, SolarWindSummary, SwpcBulletin

SWPC_BASE = "https://services.swpc.noaa.gov"


def _parse_swpc_ts(raw: str) -> datetime:
    """SWPC timestamps come in several shapes; normalize to aware UTC."""
    cleaned = raw.replace("Z", "+00:00").replace(" UTC", "")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S.%f")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fnum(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class SwpcClient(BaseSourceClient):
    def __init__(self, **kwargs) -> None:
        super().__init__(base_url=SWPC_BASE, **kwargs)

    async def get_latest_kp(self) -> KpReading | None:
        data = await self._get_json("/json/planetary_k_index_1m.json")
        if not isinstance(data, list) or not data:
            return None
        row = data[-1]  # newest last
        return KpReading(
            time_tag=_parse_swpc_ts(str(row["time_tag"])),
            kp_index=float(row.get("estimated_kp", row.get("kp_index", 0.0))),
        )

    async def get_solar_wind(self) -> SolarWindSummary | None:
        speed = await self._get_json("/products/summary/solar-wind-speed.json")
        mag = await self._get_json("/products/summary/solar-wind-mag-field.json")
        if not isinstance(speed, dict):
            return None
        return SolarWindSummary(
            time_tag=_parse_swpc_ts(str(speed.get("TimeStamp"))),
            wind_speed_km_s=_fnum(speed.get("WindSpeed")),
            bt_nt=_fnum(mag.get("Bt")) if isinstance(mag, dict) else None,
            bz_nt=_fnum(mag.get("Bz")) if isinstance(mag, dict) else None,
        )

    async def get_bulletins(self, limit: int = 20) -> list[SwpcBulletin]:
        data = await self._get_json("/products/alerts.json")
        if not isinstance(data, list):
            return []
        return [
            SwpcBulletin(
                product_id=str(row.get("product_id", "SWPC")),
                issue_datetime=_parse_swpc_ts(str(row["issue_datetime"])),
                message=str(row.get("message", "")).strip(),
            )
            for row in data[:limit]
        ]
