import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FleetSummary, MissionAssurance, MissionGraph } from "@/lib/types";
import { Card, PageHeader, ScoreBar } from "@/components/ui";

const NODE_FILL: Record<string, string> = {
  operational: "#10B981", degraded: "#F59E0B", offline: "#EF4444", unknown: "#64748B",
};

function Graph({ graph }: { graph: MissionGraph }) {
  const mission = graph.nodes.find((n) => n.kind === "mission");
  const assets = graph.nodes.filter((n) => n.kind === "asset");
  const H = Math.max(260, assets.length * 84 + 40);
  const pos = new Map<string, { x: number; y: number }>();
  if (mission) pos.set(mission.id, { x: 120, y: H / 2 });
  assets.forEach((a, i) => pos.set(a.id, { x: 520, y: 52 + i * 84 }));

  return (
    <svg viewBox={`0 0 680 ${H}`} className="w-full">
      {graph.edges.map((e, i) => {
        const s = pos.get(e.source); const t = pos.get(e.target);
        if (!s || !t) return null;
        const dash = e.kind === "asset_dependency" ? "4 4" : undefined;
        const stroke = e.criticality === "critical" ? "#EF4444"
          : e.criticality === "high" ? "#F59E0B" : "#1F2A44";
        const mx = (s.x + t.x) / 2;
        return (
          <path key={i} d={`M ${s.x} ${s.y} C ${mx} ${s.y}, ${mx} ${t.y}, ${t.x} ${t.y}`}
            fill="none" stroke={stroke} strokeWidth={1.5} strokeDasharray={dash} opacity={0.8} />
        );
      })}
      {mission && (
        <g transform={`translate(${pos.get(mission.id)?.x ?? 0} ${pos.get(mission.id)?.y ?? 0})`}>
          <rect x={-95} y={-26} width={190} height={52} rx={8}
            fill="#111827" stroke="#2563EB" strokeWidth={1.5} />
          <text textAnchor="middle" y={-4} fill="#E5E7EB" fontSize={13} fontWeight={600}>
            {mission.label}
          </text>
          <text textAnchor="middle" y={14} fill="#64748B" fontSize={10}
            style={{ textTransform: "uppercase" }}>mission</text>
        </g>
      )}
      {assets.map((a) => {
        const p = pos.get(a.id);
        if (!p) return null;
        return (
          <g key={a.id} transform={`translate(${p.x} ${p.y})`}>
            <rect x={-10} y={-24} width={170} height={48} rx={6}
              fill="#111827" stroke="#1F2A44" />
            <circle cx={4} cy={0} r={4} fill={NODE_FILL[a.status ?? "unknown"]} />
            <text x={16} y={-2} fill="#E5E7EB" fontSize={11.5}>
              {a.label.length > 20 ? `${a.label.slice(0, 19)}…` : a.label}
            </text>
            <text x={16} y={13} fill="#64748B" fontSize={9.5}>
              {a.status} · {a.criticality}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function MissionIQ() {
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [selected, setSelected] = useState<MissionAssurance | null>(null);
  const [graph, setGraph] = useState<MissionGraph | null>(null);

  useEffect(() => {
    api.fleet().then((f) => {
      setFleet(f);
      if (f.missions.length > 0 && f.missions[0]) select(f.missions[0]);
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function select(m: MissionAssurance) {
    setSelected(m);
    api.missionGraph(m.mission_id).then(setGraph).catch(() => setGraph(null));
  }

  const tone = (s: number) => (s >= 80 ? "text-mission" : s >= 50 ? "text-amber" : "text-critical");

  return (
    <div>
      <PageHeader question="Can the mission still succeed?" title="MissionIQ" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Missions
          </h2>
          <ul className="space-y-2">
            {fleet?.missions.map((m) => (
              <li key={m.mission_id}>
                <button onClick={() => select(m)}
                  className={`w-full rounded border p-3 text-left ${
                    selected?.mission_id === m.mission_id
                      ? "border-orbital bg-orbital/10" : "border-line bg-navy hover:border-orbital/50"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{m.name}</span>
                    <span className={`telemetry ${tone(m.score)}`}>{m.score}</span>
                  </div>
                  <div className="mt-2"><ScoreBar score={m.score} /></div>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-2">
          {selected && (
            <>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-faint">
                  Dependency graph — {selected.name}
                </h2>
                <span className="text-xs capitalize text-ink-muted">
                  {selected.health.replace("_", " ")} · {selected.asset_count} assets ·{" "}
                  {selected.open_alerts} open alerts
                </span>
              </div>
              {graph ? <Graph graph={graph} /> :
                <p className="text-sm text-ink-muted">Loading graph…</p>}
              <h3 className="mt-4 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                Assurance factors (explainable score)
              </h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-muted">
                {selected.factors.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </>
          )}
          {!selected && <p className="text-sm text-ink-muted">Select a mission.</p>}
        </Card>
      </div>
    </div>
  );
}
