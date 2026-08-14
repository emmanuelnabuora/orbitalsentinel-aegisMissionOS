"""SentinelAI engine: incident analysis and mission-context chat.

All reasoning is grounded in platform data fetched here — the provider only
shapes language. With no LLM configured, structured rule-based output is
returned; it is deterministic and fully explainable.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.models.incident import IncidentEvent
from aegis_api.repositories.alerts import AlertRepository
from aegis_api.schemas.sentinel import ChatResponse, IncidentAnalysis
from aegis_api.services.audit import AuditService
from aegis_api.services.incidents import IncidentService
from aegis_api.services.missioniq import MissionIQService
from aegis_api.services.quantum import QuantumService
from aegis_api.services.sentinel.providers import (
    ProviderError,
    RuleBasedProvider,
    get_provider,
)


class SentinelService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.incidents = IncidentService(session)
        self.alerts = AlertRepository(session)
        self.missioniq = MissionIQService(session)
        self.quantum = QuantumService(session)
        self.audit = AuditService(session)
        self.provider = get_provider()

    async def analyze_incident(
        self, incident_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> IncidentAnalysis:
        incident = await self.incidents.get(incident_id)
        linked, _ = await self.alerts.list(limit=100, offset=0, incident_id=incident.id)

        affected = sorted({a.asset.name for a in linked if a.asset})
        severities = [a.severity.value for a in linked]

        summary_parts = [
            f"Incident '{incident.title}' ({incident.severity.value}) is {incident.status.value}."
        ]
        if linked:
            summary_parts.append(
                f"{len(linked)} linked alert(s) [{', '.join(sorted(set(severities)))}]"
                + (f" affecting: {', '.join(affected)}." if affected else ".")
            )
        else:
            summary_parts.append("No alerts are linked yet; evidence base is thin.")
        if incident.summary:
            summary_parts.append(f"Commander summary: {incident.summary}")

        hypotheses: list[str] = []
        titles = " ".join(a.title.lower() for a in linked)
        if any(k in titles for k in ("telemetry", "signal", "rf", "link")):
            hypotheses.append(
                "Communications-path degradation (RF interference, ground-station fault, "
                "or link-layer attack) — telemetry/link alerts present."
            )
        if any(k in titles for k in ("auth", "login", "credential", "access")):
            hypotheses.append("Credential compromise or access-control failure.")
        if any(k in titles for k in ("cert", "tls", "crypto", "expir")):
            hypotheses.append("Cryptographic/certificate fault in the trust chain.")
        if not hypotheses:
            hypotheses.append(
                "Insufficient signal for a confident hypothesis; broaden evidence collection."
            )

        actions = [
            "Verify current status of affected assets and their mission dependencies.",
            "Assign an analyst to each unassigned linked alert.",
        ]
        if affected:
            actions.append(
                f"Run MissionIQ impact review for missions depending on: {', '.join(affected)}."
            )
        if incident.status.value == "open":
            actions.append("Move the incident to 'investigating' and set a commander.")

        analysis = IncidentAnalysis(
            summary=" ".join(summary_parts),
            root_cause_hypotheses=hypotheses,
            recommended_actions=actions,
            provider=self.provider.name,
        )

        if not isinstance(self.provider, RuleBasedProvider):
            system = (
                "You are SentinelAI, a mission-assurance analyst. Refine the draft "
                "analysis. Be concise, factual, and ground every claim in the given data."
            )
            try:
                refined = await self.provider.complete(system, analysis.summary)
                analysis.summary = refined or analysis.summary
            except ProviderError:
                # Fail-open: the deterministic draft ships; note the fallback.
                analysis.provider = f"{analysis.provider} (degraded->rules)"

        self.session.add(
            IncidentEvent(
                incident_id=incident.id,
                kind="ai_analysis",
                message=f"SentinelAI analysis generated ({analysis.provider}).",
                actor_id=actor_id,
            )
        )
        self.audit.record(
            actor_id=actor_id,
            action="sentinel.incident_analyzed",
            resource_type="incident",
            resource_id=incident.id,
            detail={"provider": analysis.provider},
        )
        await self.session.commit()
        return analysis

    async def chat(self, message: str, *, actor_id: uuid.UUID) -> ChatResponse:
        text = message.lower()
        fleet = await self.missioniq.fleet()

        if any(k in text for k in ("mission", "assurance", "succeed")):
            worst = min(fleet.missions, key=lambda m: m.score, default=None)
            answer = (
                f"Fleet assurance averages {fleet.average_score}/100 across "
                f"{len(fleet.missions)} mission(s)."
            )
            if worst is not None:
                answer += f" Lowest: {worst.name} at {worst.score} ({worst.health}) — " + " ".join(
                    worst.factors[:2]
                )
            actions = ["Open MissionIQ for the full dependency graph and factor breakdown."]
        elif any(k in text for k in ("quantum", "pqc", "crypto", "cert")):
            q = await self.quantum.readiness()
            answer = (
                f"PQC readiness is {q.score}/100: {q.pqc_ready_records} of "
                f"{q.total_records} crypto records are quantum-resistant; "
                f"{q.vulnerable_records} vulnerable."
            )
            actions = q.recommendations[:3]
        elif any(k in text for k in ("indicator", "ioc", "intel", "targeting")):
            from aegis_api.services.threatintel.engine import ThreatIntelService

            ti = await ThreatIntelService(self.session).summary()
            worst = max(ti.by_severity, key=lambda k: ti.by_severity[k], default=None)
            answer = (
                f"{ti.active_indicators} active threat indicator(s) tracked from "
                f"{len(ti.sources)} source(s); {ti.total_matches} correlated to our "
                f"assets." + (f" Largest severity band: {worst}." if worst else "")
            )
            actions = ["Open Threat Intelligence and run correlation against the fleet."]
        elif any(k in text for k in ("alert", "attention", "threat")):
            answer = (
                f"{fleet.open_alerts} open alert(s); threat level {fleet.threat_level}; "
                f"{fleet.open_incidents} open incident(s)."
            )
            actions = ["Triage unassigned alerts in the Alerts Center, highest severity first."]
        elif any(k in text for k in ("status", "happening", "overview", "summary")):
            answer = (
                f"Operational picture: {fleet.total_assets} assets, "
                f"{len(fleet.missions)} missions (avg assurance {fleet.average_score}), "
                f"{fleet.open_alerts} open alerts, {fleet.open_incidents} open incidents. "
                f"Threat level: {fleet.threat_level}."
            )
            actions = ["Ask about missions, alerts, or quantum readiness for detail."]
        else:
            answer = (
                "I can report on mission assurance, alerts and threat level, incidents, "
                "and quantum readiness — all grounded in live platform data."
            )
            actions = ["Try: 'what is our mission assurance?' or 'are we quantum ready?'"]

        provider_name = self.provider.name
        if not isinstance(self.provider, RuleBasedProvider):
            try:
                refined = await self.provider.complete(
                    "You are SentinelAI. Answer using ONLY the grounded data provided.",
                    f"Data: {answer}\n\nUser question: {message}",
                )
                answer = refined or answer
            except ProviderError:
                # Fail-open: the deterministic answer ships; the tag makes
                # the degradation visible instead of silently invisible.
                provider_name = f"{provider_name} (degraded->rules)"

        self.audit.record(
            actor_id=actor_id, action="sentinel.chat", detail={"provider": provider_name}
        )
        await self.session.commit()
        return ChatResponse(answer=answer, provider=provider_name, suggested_actions=actions)
