"""MissionIQ: mission assurance scoring.

Deterministic, explainable v1 model (Explainable AI principle: every score
ships with human-readable factors). Signals: asset operational status
weighted by dependency criticality, plus open alerts on mission assets.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.repositories.alerts import AlertRepository
from aegis_api.repositories.assets import AssetRepository
from aegis_api.repositories.incidents import IncidentRepository
from aegis_api.schemas.missioniq import FleetSummary, MissionAssurance
from aegis_api.services.missions import MissionService
from aegis_api.services.scoring import ScoredAsset, score_mission


class MissionIQService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.missions = MissionService(session)
        self.assets = AssetRepository(session)
        self.alerts = AlertRepository(session)
        self.incidents = IncidentRepository(session)

    async def assurance(self, mission_id: uuid.UUID) -> MissionAssurance:
        mission = await self.missions.get(mission_id)
        links = mission.asset_links
        asset_ids = {link.asset_id for link in links}
        open_alerts = await self.alerts.open_by_asset(asset_ids)

        scored = [
            ScoredAsset(
                name=link.asset.name,
                status=link.asset.status,
                dependency_criticality=link.dependency_criticality,
                open_alerts=open_alerts.get(link.asset_id, 0),
            )
            for link in links
        ]
        result = score_mission(scored)

        return MissionAssurance(
            mission_id=mission.id,
            name=mission.name,
            status=mission.status,
            score=result.score,
            health=result.health,
            asset_count=len(links),
            degraded_assets=result.degraded_assets,
            offline_assets=result.offline_assets,
            open_alerts=result.open_alerts,
            factors=result.factors,
        )

    async def fleet(self) -> FleetSummary:
        missions, _ = await self.missions.repo.list(limit=100, offset=0)
        assurances = [await self.assurance(m.id) for m in missions]
        avg = round(sum(a.score for a in assurances) / len(assurances)) if assurances else 100

        open_critical = await self.alerts.count_open()
        from aegis_api.models.enums import AlertSeverity

        critical_alerts = await self.alerts.count_open(severity=AlertSeverity.CRITICAL)
        threat = (
            "severe"
            if critical_alerts >= 3
            else "high"
            if critical_alerts >= 1
            else "elevated"
            if open_critical >= 3
            else "low"
        )

        _, total_assets = await self.assets.list(limit=1, offset=0)
        return FleetSummary(
            average_score=avg,
            threat_level=threat,
            missions=assurances,
            total_assets=total_assets,
            open_alerts=open_critical,
            open_incidents=await self.incidents.count_open(),
        )
