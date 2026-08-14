"""Reporting engine: assembles structured report snapshots from live data.

Each report kind pulls current platform state through the same services the UI
uses, so a report never diverges from what operators see. The narrative summary
is produced by SentinelAI (rule-based by default, LLM when configured); the
factual sections and tables are assembled deterministically here. Snapshots are
immutable once written.
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api.core.exceptions import NotFoundError, ValidationFailure
from aegis_api.models.enums import ReportKind
from aegis_api.models.report import Report
from aegis_api.schemas.report import (
    ReportContent,
    ReportGenerate,
    ReportSection,
)
from aegis_api.services.audit import AuditService
from aegis_api.services.incidents import IncidentService
from aegis_api.services.missioniq import MissionIQService
from aegis_api.services.quantum import QuantumService
from aegis_api.services.sentinel.engine import SentinelService
from aegis_api.services.threatintel.engine import ThreatIntelService

_DEFAULT_TITLES = {
    ReportKind.EXECUTIVE: "Executive Mission Assurance Summary",
    ReportKind.MISSION_ASSURANCE: "Mission Assurance Report",
    ReportKind.INCIDENT: "Incident Report",
    ReportKind.THREAT_INTEL: "Threat Intelligence Briefing",
    ReportKind.QUANTUM_READINESS: "Quantum Readiness Assessment",
}


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)
        self.missioniq = MissionIQService(session)
        self.quantum = QuantumService(session)
        self.threatintel = ThreatIntelService(session)
        self.incidents = IncidentService(session)
        self.sentinel = SentinelService(session)

    async def generate(self, data: ReportGenerate, *, actor_id: uuid.UUID) -> Report:
        builder = {
            ReportKind.EXECUTIVE: self._executive,
            ReportKind.MISSION_ASSURANCE: self._mission_assurance,
            ReportKind.INCIDENT: self._incident,
            ReportKind.THREAT_INTEL: self._threat_intel,
            ReportKind.QUANTUM_READINESS: self._quantum,
        }[data.kind]
        content, subject_id = await builder(data, actor_id)

        title = data.title or _DEFAULT_TITLES[data.kind]
        report = Report(
            kind=data.kind,
            title=title,
            subject_id=subject_id,
            content=content.model_dump(),
            provider=self.sentinel.provider.name,
            generated_by=actor_id,
        )
        self.session.add(report)
        await self.session.flush()
        self.audit.record(
            actor_id=actor_id,
            action="report.generated",
            resource_type="report",
            resource_id=report.id,
            detail={"kind": data.kind.value},
        )
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def get(self, report_id: uuid.UUID) -> Report:
        report = await self.session.get(Report, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        return report

    async def list(
        self, *, limit: int, offset: int, kind: ReportKind | None = None
    ) -> tuple[list[Report], int]:
        conditions = []
        if kind is not None:
            conditions.append(Report.kind == kind)
        total = (
            await self.session.execute(sa.select(sa.func.count(Report.id)).where(*conditions))
        ).scalar_one()
        rows = (
            await self.session.execute(
                sa.select(Report)
                .where(*conditions)
                .order_by(Report.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return list(rows), total

    # ── builders ──

    def _stamp(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    async def _narrative(self, prompt: str, actor_id: uuid.UUID) -> str:
        resp = await self.sentinel.chat(prompt, actor_id=actor_id)
        return resp.answer

    async def _executive(
        self, _data: ReportGenerate, actor_id: uuid.UUID
    ) -> tuple[ReportContent, None]:
        fleet = await self.missioniq.fleet()
        quantum = await self.quantum.readiness()
        ti = await self.threatintel.summary()
        summary = await self._narrative("overview", actor_id)

        posture = ReportSection(
            heading="Overall Posture",
            body=(
                f"As of {self._stamp()}, fleet mission assurance averages "
                f"{fleet.average_score}/100 across {len(fleet.missions)} tracked mission(s). "
                f"Threat level is {fleet.threat_level.upper()} with {fleet.open_alerts} open "
                f"alert(s) and {fleet.open_incidents} open incident(s). Quantum readiness "
                f"stands at {quantum.score}/100. {ti.active_indicators} threat indicator(s) "
                f"are actively tracked, with {ti.total_matches} correlated to our assets."
            ),
        )
        missions = ReportSection(
            heading="Mission Assurance",
            columns=["Mission", "Score", "Health", "Open Alerts"],
            rows=[[m.name, str(m.score), m.health, str(m.open_alerts)] for m in fleet.missions]
            or [["No missions tracked", "-", "-", "-"]],
        )
        risks = ReportSection(
            heading="Key Risk Factors",
            body=self._risk_lines(fleet),
        )
        return ReportContent(summary=summary, sections=[posture, missions, risks]), None

    def _risk_lines(self, fleet) -> str:
        at_risk = [m for m in fleet.missions if m.health != "assured"]
        if not at_risk:
            return "All tracked missions are within assured tolerances."
        lines = []
        for m in at_risk:
            top = "; ".join(m.factors[:2]) if m.factors else "see MissionIQ for detail"
            lines.append(f"{m.name} ({m.health}, {m.score}/100): {top}.")
        return " ".join(lines)

    async def _mission_assurance(
        self, _data: ReportGenerate, actor_id: uuid.UUID
    ) -> tuple[ReportContent, None]:
        fleet = await self.missioniq.fleet()
        summary = await self._narrative("what is our mission assurance?", actor_id)
        sections = [
            ReportSection(
                heading="Fleet Overview",
                body=(
                    f"Average assurance {fleet.average_score}/100 across "
                    f"{len(fleet.missions)} mission(s). Threat level "
                    f"{fleet.threat_level.upper()}."
                ),
            )
        ]
        for m in fleet.missions:
            sections.append(
                ReportSection(
                    heading=f"{m.name} — {m.score}/100 ({m.health})",
                    body=(
                        f"{m.asset_count} asset(s); {m.degraded_assets} degraded, "
                        f"{m.offline_assets} offline; {m.open_alerts} open alert(s)."
                    ),
                    columns=["Assurance Factor"] if m.factors else None,
                    rows=[[f] for f in m.factors] if m.factors else None,
                )
            )
        return ReportContent(summary=summary, sections=sections), None

    async def _incident(
        self, data: ReportGenerate, actor_id: uuid.UUID
    ) -> tuple[ReportContent, uuid.UUID]:
        if data.subject_id is None:
            raise ValidationFailure("subject_id (incident) is required for incident reports")
        incident = await self.incidents.get(data.subject_id)
        analysis = await self.sentinel.analyze_incident(incident.id, actor_id=actor_id)
        linked, _ = await self.incidents.alerts.list(limit=100, offset=0, incident_id=incident.id)
        timeline = ReportSection(
            heading="Timeline",
            columns=["When", "Event", "Detail"],
            rows=[[e.at.strftime("%Y-%m-%d %H:%M"), e.kind, e.message] for e in incident.events],
        )
        evidence = ReportSection(
            heading="Linked Alerts (Evidence)",
            columns=["Severity", "Alert", "Asset"],
            rows=[[a.severity.value, a.title, a.asset.name if a.asset else "-"] for a in linked]
            or [["-", "No alerts linked", "-"]],
        )
        rca = ReportSection(
            heading="Root-Cause Analysis",
            body=" ".join(analysis.root_cause_hypotheses),
        )
        response = ReportSection(
            heading="Response Plan",
            columns=["Recommended Action"],
            rows=[[a] for a in analysis.recommended_actions],
        )
        content = ReportContent(
            summary=analysis.summary,
            sections=[
                ReportSection(
                    heading="Incident Overview",
                    body=(
                        f"'{incident.title}' — severity {incident.severity.value}, "
                        f"status {incident.status.value}. Report generated "
                        f"{self._stamp()}."
                    ),
                ),
                timeline,
                evidence,
                rca,
                response,
            ],
        )
        return content, incident.id

    async def _threat_intel(
        self, _data: ReportGenerate, actor_id: uuid.UUID
    ) -> tuple[ReportContent, None]:
        ti = await self.threatintel.summary()
        matches = await self.threatintel.list_matches(limit=100)
        summary = await self._narrative("what threat indicators are we tracking?", actor_id)
        overview = ReportSection(
            heading="Intelligence Overview",
            body=(
                f"{ti.active_indicators} active indicator(s) from "
                f"{len(ti.sources)} source(s) as of {self._stamp()}. "
                f"{ti.total_matches} correlated to our infrastructure."
            ),
        )
        by_sev = ReportSection(
            heading="Indicators by Severity",
            columns=["Severity", "Count"],
            rows=[[k, str(v)] for k, v in sorted(ti.by_severity.items())] or [["-", "0"]],
        )
        observed = ReportSection(
            heading="Observed on Our Assets",
            columns=["Asset", "Indicator", "Matched Attribute"],
            rows=[
                [
                    m.asset.name if m.asset else "-",
                    m.indicator.value if m.indicator else "-",
                    m.matched_on,
                ]
                for m in matches
            ]
            or [["None", "-", "-"]],
        )
        return ReportContent(summary=summary, sections=[overview, by_sev, observed]), None

    async def _quantum(
        self, _data: ReportGenerate, actor_id: uuid.UUID
    ) -> tuple[ReportContent, None]:
        q = await self.quantum.readiness()
        summary = await self._narrative("are we quantum ready?", actor_id)
        overview = ReportSection(
            heading="Readiness Overview",
            body=(
                f"PQC readiness {q.score}/100 as of {self._stamp()}: "
                f"{q.pqc_ready_records} of {q.total_records} crypto record(s) are "
                f"quantum-resistant; {q.vulnerable_records} vulnerable."
            ),
        )
        vuln = ReportSection(
            heading="Vulnerable Algorithms",
            columns=["Algorithm", "Count"],
            rows=[[k, str(v)] for k, v in sorted(q.vulnerable_by_algorithm.items())]
            or [["None", "0"]],
        )
        plan = ReportSection(
            heading="Migration Plan",
            columns=["Recommended Action"],
            rows=[[r] for r in q.recommendations],
        )
        return ReportContent(summary=summary, sections=[overview, vuln, plan]), None
