"""Threat intelligence engine: ingestion, correlation, and alerting.

Correlation walks every asset's attributes (flattened to strings) and matches
them against active indicators. A hit creates a ThreatMatch and raises a real
Alert into the standard pipeline — threat intel is not a separate silo; it
feeds the same triage workflow operators already use. Matching is idempotent:
one (indicator, asset) pair produces exactly one match and one alert.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.alert import Alert
from aegis_api.models.enums import AlertSeverity, IndicatorType, ThreatCategory
from aegis_api.models.threatintel import ThreatIndicator, ThreatMatch
from aegis_api.repositories.assets import AssetRepository
from aegis_api.schemas.threatintel import (
    CorrelationResult,
    IndicatorCreate,
    IngestResult,
    ThreatIntelSummary,
    ThreatMatchRead,
)
from aegis_api.services.audit import AuditService
from aegis_api.services.threatintel.feeds import CuratedFeedProvider, FeedProvider


def _flatten_strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Yield (attribute_path, string_value) pairs from nested attributes."""
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out.extend(_flatten_strings(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.extend(_flatten_strings(v, f"{path}[{i}]"))
    elif isinstance(value, str):
        out.append((path, value.strip().lower()))
    return out


def match_to_read(m: ThreatMatch) -> ThreatMatchRead:
    data = ThreatMatchRead.model_validate(m)
    if m.indicator:
        data.indicator_value = m.indicator.value
        data.indicator_category = m.indicator.category
        data.severity = m.indicator.severity
    if m.asset:
        data.asset_name = m.asset.name
    return data


class ThreatIntelService:
    def __init__(self, session: AsyncSession, providers: list[FeedProvider] | None = None):
        self.session = session
        self.assets = AssetRepository(session)
        self.audit = AuditService(session)
        self.providers = providers if providers is not None else [CuratedFeedProvider()]

    # ── indicators ──

    async def register(self, data: IndicatorCreate, *, actor_id: uuid.UUID) -> ThreatIndicator:
        indicator, created = await self._upsert(data.model_dump(), source=data.source)
        self.audit.record(
            actor_id=actor_id,
            action="threatintel.indicator_registered"
            if created
            else "threatintel.indicator_updated",
            resource_type="threat_indicator",
            resource_id=indicator.id,
        )
        await self.session.commit()
        await self.session.refresh(indicator)
        return indicator

    async def list_indicators(
        self,
        *,
        limit: int,
        offset: int,
        indicator_type: IndicatorType | None = None,
        severity: AlertSeverity | None = None,
        active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[ThreatIndicator], int]:
        conditions = []
        if indicator_type is not None:
            conditions.append(ThreatIndicator.indicator_type == indicator_type)
        if severity is not None:
            conditions.append(ThreatIndicator.severity == severity)
        if active is not None:
            conditions.append(ThreatIndicator.active == active)
        if search:
            like = f"%{search.lower()}%"
            conditions.append(
                sa.or_(
                    sa.func.lower(ThreatIndicator.value).like(like),
                    sa.func.lower(ThreatIndicator.description).like(like),
                )
            )
        total = (
            await self.session.execute(
                sa.select(sa.func.count(ThreatIndicator.id)).where(*conditions)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                sa.select(ThreatIndicator)
                .where(*conditions)
                .order_by(ThreatIndicator.last_seen.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return list(rows), total

    async def _upsert(self, data: dict[str, Any], *, source: str) -> tuple[ThreatIndicator, bool]:
        """Insert or refresh an indicator; identity is (type, value)."""
        value = str(data["value"]).strip()
        existing = (
            await self.session.execute(
                sa.select(ThreatIndicator).where(
                    ThreatIndicator.indicator_type == data["indicator_type"],
                    ThreatIndicator.value == value,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.last_seen = datetime.now(UTC)
            existing.confidence = max(existing.confidence, int(data.get("confidence", 0)))
            if data.get("description"):
                existing.description = data["description"]
            existing.active = True
            return existing, False
        indicator = ThreatIndicator(
            indicator_type=data["indicator_type"],
            value=value,
            category=data.get("category", ThreatCategory.UNKNOWN),
            severity=data["severity"],
            confidence=int(data.get("confidence", 50)),
            source=source,
            description=data.get("description"),
        )
        self.session.add(indicator)
        await self.session.flush()
        return indicator, True

    # ── ingestion ──

    async def ingest(self, *, actor_id: uuid.UUID) -> list[IngestResult]:
        results = []
        for provider in self.providers:
            raw = await provider.fetch()
            created = updated = 0
            for item in raw:
                try:
                    parsed = IndicatorCreate(**{**item, "source": provider.name})
                except ValueError:
                    continue  # malformed feed entries are skipped, never fatal
                _, was_created = await self._upsert(parsed.model_dump(), source=provider.name)
                created += was_created
                updated += not was_created
            results.append(
                IngestResult(
                    source=provider.name,
                    received=len(raw),
                    created=created,
                    updated=updated,
                )
            )
        self.audit.record(
            actor_id=actor_id,
            action="threatintel.ingest",
            detail={r.source: r.created for r in results},
        )
        await self.session.commit()
        return results

    # ── correlation ──

    async def correlate(self, *, actor_id: uuid.UUID) -> CorrelationResult:
        indicators = list(
            (
                await self.session.execute(
                    sa.select(ThreatIndicator).where(ThreatIndicator.active.is_(True))
                )
            ).scalars()
        )
        by_value: dict[str, ThreatIndicator] = {i.value.lower(): i for i in indicators}

        assets, _ = await self.assets.list(limit=10000, offset=0)
        existing_pairs = {
            (m.indicator_id, m.asset_id)
            for m in (await self.session.execute(sa.select(ThreatMatch))).scalars()
        }

        new_matches: list[ThreatMatch] = []
        alerts_raised = 0
        for asset in assets:
            for attr_path, text in _flatten_strings(asset.attributes or {}):
                indicator = by_value.get(text)
                if indicator is None or (indicator.id, asset.id) in existing_pairs:
                    continue
                alert = Alert(
                    title=f"Threat indicator observed on {asset.name}: "
                    f"{indicator.category.value} ({indicator.indicator_type.value})",
                    description=(
                        f"Asset attribute '{attr_path}' matches active indicator "
                        f"'{indicator.value}' from {indicator.source} "
                        f"(confidence {indicator.confidence}). {indicator.description or ''}"
                    ).strip(),
                    severity=indicator.severity,
                    source="ThreatIntel",
                    asset_id=asset.id,
                )
                self.session.add(alert)
                await self.session.flush()
                match = ThreatMatch(
                    indicator_id=indicator.id,
                    asset_id=asset.id,
                    alert_id=alert.id,
                    matched_on=attr_path,
                )
                self.session.add(match)
                existing_pairs.add((indicator.id, asset.id))
                new_matches.append(match)
                alerts_raised += 1

        if new_matches:
            await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="threatintel.correlate",
            detail={"new_matches": len(new_matches)},
        )
        await self.session.commit()
        for m in new_matches:
            await self.session.refresh(m)
        return CorrelationResult(
            indicators_checked=len(indicators),
            assets_checked=len(assets),
            new_matches=len(new_matches),
            alerts_raised=alerts_raised,
            matches=[match_to_read(m) for m in new_matches],
        )

    async def list_matches(self, *, limit: int = 100) -> list[ThreatMatch]:
        rows = (
            await self.session.execute(
                sa.select(ThreatMatch).order_by(ThreatMatch.created_at.desc()).limit(limit)
            )
        ).scalars()
        return list(rows)

    # ── summary ──

    async def summary(self) -> ThreatIntelSummary:
        def counts(column) -> sa.Select:
            return (
                sa.select(column, sa.func.count(ThreatIndicator.id))
                .where(ThreatIndicator.active.is_(True))
                .group_by(column)
            )

        by_sev = dict((await self.session.execute(counts(ThreatIndicator.severity))).all())
        by_cat = dict((await self.session.execute(counts(ThreatIndicator.category))).all())
        by_src = dict((await self.session.execute(counts(ThreatIndicator.source))).all())
        active = (
            await self.session.execute(
                sa.select(sa.func.count(ThreatIndicator.id)).where(ThreatIndicator.active.is_(True))
            )
        ).scalar_one()
        matches = (
            await self.session.execute(sa.select(sa.func.count(ThreatMatch.id)))
        ).scalar_one()
        last = (
            await self.session.execute(sa.select(sa.func.max(ThreatIndicator.last_seen)))
        ).scalar_one_or_none()
        return ThreatIntelSummary(
            active_indicators=active,
            by_severity={k.value: v for k, v in by_sev.items()},
            by_category={k.value: v for k, v in by_cat.items()},
            total_matches=matches,
            sources=by_src,
            last_ingest=last,
        )
