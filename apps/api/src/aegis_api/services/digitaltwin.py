"""Digital Twin: what-if simulation over the live fleet.

Snapshots current mission/asset/alert state into plain values, applies a
scenario's perturbations to that in-memory copy, and rescores every mission
through the SAME scoring core MissionIQ uses (services/scoring.py). Real data
is never mutated — the twin is a read-only projection. The delta between the
live baseline and the projected state is the product: which missions degrade,
by how much, and which cross into "at risk".
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import NotFoundError
from aegis_api.models.enums import AssetStatus
from aegis_api.models.scenario import Scenario
from aegis_api.repositories.alerts import AlertRepository
from aegis_api.repositories.assets import AssetRepository
from aegis_api.schemas.digitaltwin import (
    ImpactedAsset,
    MissionProjection,
    Perturbation,
    PerturbationKind,
    ScenarioCreate,
    ScenarioSimulate,
    SimulationResult,
)
from aegis_api.services.audit import AuditService
from aegis_api.services.missions import MissionService
from aegis_api.services.scoring import ScoredAsset, score_mission


@dataclass
class _AssetState:
    """Mutable in-memory copy of an asset for one simulation run."""

    asset_id: uuid.UUID
    name: str
    status: AssetStatus
    open_alerts: int
    removed: bool = False


@dataclass
class _MissionState:
    mission_id: uuid.UUID
    name: str
    # asset_id -> dependency criticality
    links: list[tuple[uuid.UUID, object]]


class DigitalTwinService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.missions = MissionService(session)
        self.assets = AssetRepository(session)
        self.alerts = AlertRepository(session)
        self.audit = AuditService(session)

    async def _snapshot(self) -> tuple[dict[uuid.UUID, _AssetState], list[_MissionState]]:
        missions, _ = await self.missions.repo.list(limit=100, offset=0)
        mission_states: list[_MissionState] = []
        needed_assets: set[uuid.UUID] = set()
        for m in missions:
            full = await self.missions.get(m.id)
            links = [(link.asset_id, link.dependency_criticality) for link in full.asset_links]
            mission_states.append(_MissionState(mission_id=m.id, name=m.name, links=links))
            needed_assets.update(a for a, _ in links)

        open_by_asset = await self.alerts.open_by_asset(needed_assets)
        asset_states: dict[uuid.UUID, _AssetState] = {}
        for aid in needed_assets:
            asset = await self.assets.get(aid)
            if asset is None:
                continue
            asset_states[aid] = _AssetState(
                asset_id=aid,
                name=asset.name,
                status=asset.status,
                open_alerts=open_by_asset.get(aid, 0),
            )
        return asset_states, mission_states

    def _score_all(
        self,
        assets: dict[uuid.UUID, _AssetState],
        missions: list[_MissionState],
    ) -> dict[uuid.UUID, tuple[int, str, list[str]]]:
        out: dict[uuid.UUID, tuple[int, str, list[str]]] = {}
        for m in missions:
            scored = [
                ScoredAsset(
                    name=assets[aid].name,
                    status=assets[aid].status,
                    dependency_criticality=crit,
                    open_alerts=assets[aid].open_alerts,
                )
                for aid, crit in m.links
                if aid in assets and not assets[aid].removed
            ]
            r = score_mission(scored)
            out[m.mission_id] = (r.score, r.health, r.factors)
        return out

    def _apply(
        self, assets: dict[uuid.UUID, _AssetState], perturbations: list[Perturbation]
    ) -> None:
        for p in perturbations:
            state = assets.get(p.asset_id)
            if state is None:
                # Asset not attached to any mission; irrelevant to scoring.
                continue
            if p.kind == PerturbationKind.SET_STATUS and p.status is not None:
                state.status = p.status
            elif p.kind == PerturbationKind.OFFLINE:
                state.status = AssetStatus.OFFLINE
            elif p.kind == PerturbationKind.ADD_ALERTS:
                state.open_alerts += p.magnitude
            elif p.kind == PerturbationKind.REMOVE_ASSET:
                state.removed = True

    async def simulate(
        self, scenario: ScenarioSimulate, *, actor_id: uuid.UUID
    ) -> SimulationResult:
        # Validate referenced assets exist so a typo'd scenario fails loudly.
        for p in scenario.perturbations:
            if await self.assets.get(p.asset_id) is None:
                raise NotFoundError(f"Asset {p.asset_id} not found")

        baseline_assets, missions = await self._snapshot()
        baseline = self._score_all(baseline_assets, missions)

        # Deep-copy the asset snapshot for the projected run.
        projected_assets = {
            aid: _AssetState(a.asset_id, a.name, a.status, a.open_alerts, a.removed)
            for aid, a in baseline_assets.items()
        }
        self._apply(projected_assets, scenario.perturbations)
        projected = self._score_all(projected_assets, missions)

        projections: list[MissionProjection] = []
        newly_at_risk: list[str] = []
        for m in missions:
            b_score, b_health, _ = baseline[m.mission_id]
            p_score, p_health, p_factors = projected[m.mission_id]
            crossed = b_health != p_health
            if b_health != "at_risk" and p_health == "at_risk":
                newly_at_risk.append(m.name)
            projections.append(
                MissionProjection(
                    mission_id=m.mission_id,
                    name=m.name,
                    baseline_score=b_score,
                    projected_score=p_score,
                    delta=p_score - b_score,
                    baseline_health=b_health,
                    projected_health=p_health,
                    crossed_threshold=crossed,
                    projected_factors=p_factors,
                )
            )

        impacted = self._impacted(baseline_assets, projected_assets)
        b_avg = round(sum(s for s, _, _ in baseline.values()) / len(baseline)) if baseline else 100
        p_avg = (
            round(sum(s for s, _, _ in projected.values()) / len(projected)) if projected else 100
        )
        at_risk_before = sum(1 for _, h, _ in baseline.values() if h == "at_risk")
        at_risk_after = sum(1 for _, h, _ in projected.values() if h == "at_risk")

        result = SimulationResult(
            scenario_name=scenario.name,
            baseline_average=b_avg,
            projected_average=p_avg,
            average_delta=p_avg - b_avg,
            missions_at_risk_before=at_risk_before,
            missions_at_risk_after=at_risk_after,
            newly_at_risk=newly_at_risk,
            impacted_assets=impacted,
            missions=sorted(projections, key=lambda x: x.delta),
            summary=self._summary(scenario, p_avg - b_avg, newly_at_risk, impacted),
        )

        self.audit.record(
            actor_id=actor_id,
            action="digitaltwin.simulate",
            detail={"scenario": scenario.name, "average_delta": result.average_delta},
        )
        await self.session.commit()
        return result

    def _impacted(
        self,
        baseline: dict[uuid.UUID, _AssetState],
        projected: dict[uuid.UUID, _AssetState],
    ) -> list[ImpactedAsset]:
        out: list[ImpactedAsset] = []
        for aid, b in baseline.items():
            p = projected[aid]
            if b.status == p.status and b.open_alerts == p.open_alerts and not p.removed:
                continue
            out.append(
                ImpactedAsset(
                    asset_id=aid,
                    name=b.name,
                    baseline_status=b.status.value,
                    projected_status=p.status.value,
                    removed=p.removed,
                    added_alerts=max(0, p.open_alerts - b.open_alerts),
                )
            )
        return out

    def _summary(
        self,
        scenario: ScenarioSimulate,
        avg_delta: int,
        newly_at_risk: list[str],
        impacted: list[ImpactedAsset],
    ) -> str:
        """Deterministic, grounded narrative of the projected impact."""
        parts = [f"Scenario '{scenario.name}' perturbs {len(impacted)} mission-relevant asset(s)."]
        if avg_delta == 0:
            parts.append("Projected fleet assurance is unchanged.")
        else:
            direction = "drops" if avg_delta < 0 else "rises"
            parts.append(f"Projected fleet assurance {direction} by {abs(avg_delta)} point(s).")
        if newly_at_risk:
            parts.append(
                f"{len(newly_at_risk)} mission(s) would cross into AT-RISK: "
                f"{', '.join(newly_at_risk)}."
            )
        else:
            parts.append("No missions cross into at-risk under this scenario.")
        return " ".join(parts)

    # ── saved scenarios ──

    async def create_scenario(self, data: ScenarioCreate, *, actor_id: uuid.UUID) -> Scenario:
        scenario = Scenario(
            name=data.name,
            description=data.description,
            perturbations=[p.model_dump(mode="json") for p in data.perturbations],
            created_by=actor_id,
        )
        self.session.add(scenario)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="scenario.created",
            resource_type="scenario",
            resource_id=scenario.id,
        )
        await self.session.commit()
        await self.session.refresh(scenario)
        return scenario

    async def list_scenarios(self) -> list[Scenario]:
        rows = (
            await self.session.execute(sa.select(Scenario).order_by(Scenario.created_at.desc()))
        ).scalars()
        return list(rows)

    async def get_scenario(self, scenario_id: uuid.UUID) -> Scenario:
        scenario = await self.session.get(Scenario, scenario_id)
        if scenario is None:
            raise NotFoundError("Scenario not found")
        return scenario

    async def delete_scenario(self, scenario_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        scenario = await self.get_scenario(scenario_id)
        await self.session.delete(scenario)
        self.audit.record(
            actor_id=actor_id,
            action="scenario.deleted",
            resource_type="scenario",
            resource_id=scenario_id,
        )
        await self.session.commit()

    async def run_scenario(
        self, scenario_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> SimulationResult:
        scenario = await self.get_scenario(scenario_id)
        # Stored dicts re-validate into Perturbation via ScenarioSimulate.
        request = ScenarioSimulate(name=scenario.name, perturbations=scenario.perturbations)
        result = await self.simulate(request, actor_id=actor_id)
        scenario.last_run_at = datetime.now(UTC)
        await self.session.commit()
        return result
