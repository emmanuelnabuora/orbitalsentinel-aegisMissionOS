import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { Alert, ChatResponse, FleetSummary, QuantumReadiness } from "@/lib/types";
import { Card, PageHeader, ScoreBar, SeverityBadge, Stat, StatusDot, timeAgo } from "@/components/ui";

export default function Dashboard() {
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [quantum, setQuantum] = useState<QuantumReadiness | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [brief, setBrief] = useState<ChatResponse | null>(null);

  useEffect(() => {
    api.fleet().then(setFleet).catch(() => undefined);
    api.quantumReadiness().then(setQuantum).catch(() => undefined);
    api.alerts("?limit=5").then((p) => setAlerts(p.items)).catch(() => undefined);
    api.sentinelChat("overview").then(setBrief).catch(() => undefined);
  }, []);

  const scoreTone = (s: number) => (s >= 80 ? "text-mission" : s >= 50 ? "text-amber" : "text-critical");
  const threatTone: Record<string, string> = {
    low: "text-mission", elevated: "text-amber", high: "text-amber", severe: "text-critical",
  };

  return (
    <div>
      <PageHeader question="What is happening now?" title="Executive Dashboard" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Stat label="Mission Assurance" value={fleet ? `${fleet.average_score}` : "—"}
          tone={fleet ? scoreTone(fleet.average_score) : undefined}
          sub={fleet ? `${fleet.missions.length} mission(s) tracked` : undefined} />
        <Stat label="Threat Level" value={fleet ? fleet.threat_level.toUpperCase() : "—"}
          tone={fleet ? threatTone[fleet.threat_level] : undefined}
          sub={fleet ? `${fleet.open_alerts} open alert(s)` : undefined} />
        <Stat label="Quantum Readiness" value={quantum ? `${quantum.score}` : "—"}
          tone={quantum ? scoreTone(quantum.score) : undefined}
          sub={quantum ? `${quantum.vulnerable_records} vulnerable record(s)` : undefined} />
        <Stat label="Active Incidents" value={fleet ? fleet.open_incidents : "—"}
          tone={fleet && fleet.open_incidents > 0 ? "text-amber" : "text-mission"}
          sub={fleet ? `${fleet.total_assets} assets under protection` : undefined} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-faint">
              Latest alerts
            </h2>
            <Link to="/alerts" className="text-xs text-orbital hover:underline">Alerts Center →</Link>
          </div>
          {alerts.length === 0 && <p className="text-sm text-ink-muted">No alerts. Quiet skies.</p>}
          <ul className="divide-y divide-line">
            {alerts.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm">{a.title}</p>
                  <p className="text-xs text-ink-faint">
                    {a.source} {a.asset_name ? `· ${a.asset_name}` : ""} · {timeAgo(a.created_at)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3 text-xs">
                  <SeverityBadge value={a.severity} />
                  <StatusDot value={a.status} />
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            SentinelAI brief
          </h2>
          {brief ? (
            <>
              <p className="text-sm leading-relaxed text-ink-muted">{brief.answer}</p>
              <p className="telemetry mt-3 !text-[11px] text-ink-faint">via {brief.provider}</p>
              <Link to="/sentinel" className="mt-3 inline-block text-xs text-orbital hover:underline">
                Open copilot →
              </Link>
            </>
          ) : <p className="text-sm text-ink-muted">Generating…</p>}
        </Card>
      </div>

      {fleet && (
        <Card className="mt-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Missions
          </h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {fleet.missions.map((m) => (
              <Link key={m.mission_id} to="/missioniq"
                className="rounded border border-line bg-navy p-4 hover:border-orbital/60">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{m.name}</p>
                  <span className={`telemetry ${scoreTone(m.score)}`}>{m.score}</span>
                </div>
                <div className="mt-2"><ScoreBar score={m.score} /></div>
                <p className="mt-2 text-xs text-ink-faint">
                  {m.asset_count} assets · {m.open_alerts} open alerts · {m.health}
                </p>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
