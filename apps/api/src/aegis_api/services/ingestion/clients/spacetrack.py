"""Space-Track.org client (Phase 22).

Unlike Celestrak/SWPC, Space-Track has no API key. Authentication is a
session cookie obtained by POSTing your registered account username and
password to /ajaxauth/login; the httpx.AsyncClient's cookie jar then
carries that session on subsequent requests automatically. Session
expiry mid-use is handled by a single re-auth-and-retry.

Throttling: Space-Track explicitly asks integrators not to fire one
request per satellite — batch NORAD IDs into comma-delimited lists —
and to keep query frequency low generally. This client enforces a
minimum spacing between requests on top of that batching.

CDM (Conjunction Data Message) caveat, important for capability honesty:
the `cdm` class returns messages addressed to YOUR organization's
registered, owned spacecraft — it is not a general public conjunction
feed like Celestrak's SOCRATES. An account with no registered satellites
will legitimately see an empty result set; that is not a client bug.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone

import httpx

from aegis_api.core.logging import get_logger
from aegis_api.services.ingestion.clients.base import SourceUnavailable
from aegis_api.services.ingestion.schemas import ConjunctionRecord, GPRecord

log = get_logger("aegis.ingestion")

SPACE_TRACK_BASE = "https://www.space-track.org"
LOGIN_PATH = "/ajaxauth/login"
BASIC_QUERY = "/basicspacedata/query/class"
USER_AGENT = "AEGIS-MissionOS/1.0 (OrbitalSentinel ingestion; Space-Track integration)"


def _parse_ts(raw: str) -> datetime:
    cleaned = raw.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fnum(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


class SpaceTrackClient:
    def __init__(
        self,
        username: str,
        password: str,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_base_s: float = 1.0,
        min_request_interval_s: float = 2.0,
    ) -> None:
        self._username = username
        self._password = password
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            base_url=SPACE_TRACK_BASE,
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._min_interval_s = min_request_interval_s
        self._authenticated = False
        self._last_request_monotonic: float | None = None
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    async def _throttle(self) -> None:
        if self._last_request_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self._min_interval_s - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def _login(self) -> None:
        resp = await self._client.post(
            LOGIN_PATH,
            data={"identity": self._username, "password": self._password},
        )
        # Space-Track returns HTTP 200 with an empty body on success, and
        # a JSON {"Login":"Failed", ...}-shaped body (still HTTP 200) on
        # bad credentials -- so a 200 status alone doesn't mean success.
        text = resp.text.strip()
        if resp.status_code >= 400:
            raise SourceUnavailable(f"Space-Track login HTTP {resp.status_code}")
        if text:
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = None
            if isinstance(body, dict) and (
                "error" in {k.lower() for k in body} or "login" in {k.lower() for k in body}
            ):
                raise SourceUnavailable(f"Space-Track authentication failed: {text[:200]}")
        self._authenticated = True

    async def _get_json(self, path: str) -> object:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                await self._throttle()
                if not self._authenticated:
                    await self._login()
                self._last_request_monotonic = time.monotonic()
                resp = await self._client.get(path)
                if resp.status_code == 401:
                    # Session expired mid-use: re-auth once, then retry.
                    self._authenticated = False
                    await self._login()
                    self._last_request_monotonic = time.monotonic()
                    resp = await self._client.get(path)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                last_exc = exc
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    break
                await asyncio.sleep(self._backoff_base_s * (2**attempt))
        log.warning("spacetrack_source_unavailable", path=path, error=str(last_exc))
        raise SourceUnavailable(str(last_exc)) from last_exc

    # -- Conjunction Data Messages -------------------------------------------

    async def get_cdms(self, limit: int = 500) -> list["CdmRecord"]:
        """Fetch upcoming CDMs for your organization's registered
        satellites. Returns [] for accounts with none registered — that
        is expected, not an error (see module docstring)."""
        path = (
            f"{BASIC_QUERY}/cdm/tca/%3Enow/orderby/tca%20asc/limit/{limit}/format/json"
        )
        data = await self._get_json(path)
        if not isinstance(data, list):
            return []
        out: list[CdmRecord] = []
        for row in data:
            record = CdmRecord.from_raw(row)
            if record is not None:
                out.append(record)
        return out

    # -- GP catalog (authoritative; batched by NORAD id) ---------------------

    async def get_gp_by_catnrs(self, norad_ids: list[int]) -> list[GPRecord]:
        """Batched catalog lookup — comma-delimited per Space-Track's
        throttling guidance, never one request per satellite."""
        if not norad_ids:
            return []
        ids = ",".join(str(i) for i in norad_ids)
        path = f"{BASIC_QUERY}/gp/NORAD_CAT_ID/{ids}/orderby/NORAD_CAT_ID%20asc/format/json"
        data = await self._get_json(path)
        if not isinstance(data, list):
            return []
        return [GPRecord.model_validate(row) for row in data]


# Alias-tolerant CDM field matching. Space-Track's CDM class is a large,
# CCSDS-derived schema (60+ fields); we only need the spaceflight-safety
# core. Field names are matched case-insensitively to tolerate the kind
# of minor renames CelesTrak/Space-Track have made to other classes.
_CDM_ALIASES = {
    "cdm_id": {"cdm_id"},
    "tca": {"tca"},
    "miss_distance_m": {"miss_distance"},
    "relative_speed_m_s": {"relative_speed"},
    "collision_probability": {"collision_probability", "pc"},
    "norad_1": {"sat1_object_designator", "sat_1_id"},
    "name_1": {"sat1_object_name", "sat_1_name"},
    "norad_2": {"sat2_object_designator", "sat_2_id"},
    "name_2": {"sat2_object_name", "sat_2_name"},
}


class CdmRecord(ConjunctionRecord):
    """A CDM, normalized into the shared ConjunctionRecord shape.

    CDM reports MISS_DISTANCE in meters and RELATIVE_SPEED in m/s;
    ConjunctionRecord (built around SOCRATES) uses km and km/s, so
    from_raw() converts at parse time.
    """

    cdm_id: str

    @classmethod
    def from_raw(cls, row: dict) -> "CdmRecord | None":
        lower = {str(k).lower(): v for k, v in row.items()}

        def pick(field: str) -> object | None:
            for alias in _CDM_ALIASES[field]:
                if alias in lower and lower[alias] not in (None, ""):
                    return lower[alias]
            return None

        try:
            miss_m = _fnum(pick("miss_distance_m"))
            speed_m_s = _fnum(pick("relative_speed_m_s"))
            pc = _fnum(pick("collision_probability"))
            tca_raw = pick("tca")
            cdm_id = pick("cdm_id")
            norad_1, norad_2 = pick("norad_1"), pick("norad_2")
            if None in (miss_m, tca_raw, cdm_id, norad_1, norad_2):
                return None
            return cls(
                cdm_id=str(cdm_id),
                norad_cat_id_1=int(norad_1),
                object_name_1=str(pick("name_1") or f"OBJECT {norad_1}"),
                norad_cat_id_2=int(norad_2),
                object_name_2=str(pick("name_2") or f"OBJECT {norad_2}"),
                tca=_parse_ts(str(tca_raw)),
                min_range_km=miss_m / 1000.0,
                relative_speed_km_s=(speed_m_s or 0.0) / 1000.0,
                max_probability=pc if pc is not None else 0.0,
            )
        except (TypeError, ValueError):
            return None  # malformed row; skip, keep the feed alive
