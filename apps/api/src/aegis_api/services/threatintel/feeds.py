"""Threat feed providers.

`CuratedFeedProvider` ships a vetted starter set so the module works with zero
external dependencies — appropriate for air-gapped evaluation environments.
`JSONFeedProvider` pulls any HTTP JSON feed with a declarative field mapping
(commercial/OSINT feeds: OTX, abuse.ch, MISP exports).
"""

from typing import Any, Protocol

import httpx


class FeedProvider(Protocol):
    name: str

    async def fetch(self) -> list[dict[str, Any]]: ...


# Curated starter intelligence: representative of feeds targeting space/ground
# infrastructure. Values use documentation/reserved ranges (RFC 5737, .invalid)
# so demo data can never collide with real infrastructure.
CURATED_INDICATORS: list[dict[str, Any]] = [
    {
        "indicator_type": "ip",
        "value": "203.0.113.66",
        "category": "c2",
        "severity": "critical",
        "confidence": 92,
        "description": (
            "C2 endpoint associated with GhostSat intrusion set targeting ground segment VPNs."
        ),
    },
    {
        "indicator_type": "ip",
        "value": "198.51.100.23",
        "category": "scanner",
        "severity": "medium",
        "confidence": 74,
        "description": (
            "Persistent scanner enumerating exposed telemetry ports (Salt Typhoon-adjacent infra)."
        ),
    },
    {
        "indicator_type": "domain",
        "value": "gs-firmware-update.invalid",
        "category": "phishing",
        "severity": "high",
        "confidence": 88,
        "description": (
            "Spoofed ground-station vendor portal used in credential-harvesting campaign."
        ),
    },
    {
        "indicator_type": "file_hash",
        "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "category": "malware",
        "severity": "high",
        "confidence": 81,
        "description": "Loader observed in supply-chain compromise of EGSE tooling.",
    },
    {
        "indicator_type": "email",
        "value": "noreply@orbital-alerts.invalid",
        "category": "phishing",
        "severity": "medium",
        "confidence": 70,
        "description": (
            "Sender used in spearphishing of satellite operators (fake conjunction warnings)."
        ),
    },
    {
        "indicator_type": "ip",
        "value": "192.0.2.147",
        "category": "jamming",
        "severity": "high",
        "confidence": 65,
        "description": (
            "Control node linked to RF interference coordination near northern corridor."
        ),
    },
]


class CuratedFeedProvider:
    name = "aegis-curated"

    async def fetch(self) -> list[dict[str, Any]]:
        return [dict(i) for i in CURATED_INDICATORS]


class JSONFeedProvider:
    """Generic JSON feed with declarative field mapping."""

    def __init__(
        self,
        name: str,
        url: str,
        field_map: dict[str, str],
        defaults: dict[str, Any] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.name = name
        self.url = url
        self.field_map = field_map  # our field -> feed field
        self.defaults = defaults or {}
        self._transport = transport

    async def fetch(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30, transport=self._transport) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
            raw = resp.json()
        items = raw if isinstance(raw, list) else raw.get("indicators", [])
        out = []
        for item in items:
            mapped = {ours: item.get(theirs) for ours, theirs in self.field_map.items()}
            out.append({**self.defaults, **{k: v for k, v in mapped.items() if v is not None}})
        return out
