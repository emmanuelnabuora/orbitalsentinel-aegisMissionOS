import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { IncidentAnalysis, IncidentDetail as Detail } from "@/lib/types";
import { Card, PageHeader, SeverityBadge, StatusDot, timeAgo } from "@/components/ui";

const NEXT: Record<string, string> = {
  open: "investigating", investigating: "contained", contained: "resolved",
};

export default function IncidentDetail() {
  const { id } = useParams();
  const [incident, setIncident] = useState<Detail | null>(null);
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null);
  const [note, setNote] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(() => {
    if (id) api.incident(id).then(setIncident).catch(() => undefined);
  }, [id]);
  useEffect(load, [load]);

  if (!incident) return <p className="text-sm text-ink-muted">Loading incident…</p>;

  async function analyze() {
    if (!id) return;
    setAnalyzing(true);
    try { setAnalysis(await api.analyzeIncident(id)); load(); }
    finally { setAnalyzing(false); }
  }

  async function addNote() {
    if (!id || !note.trim()) return;
    await api.addIncidentNote(id, note.trim());
    setNote(""); load();
  }

  const next = NEXT[incident.status];

  return (
    <div>
      <PageHeader question="What happened?" title={incident.title}>
        <div className="flex items-center gap-3">
          <SeverityBadge value={incident.severity} />
          <StatusDot value={incident.status} />
          {next && (
            <button
              onClick={() => id && api.updateIncident(id, { status: next }).then(load)}
              className="rounded border border-line px-3 py-1.5 text-xs hover:border-orbital">
              Mark {next}
            </button>
          )}
          <button onClick={analyze} disabled={analyzing}
            className="flex items-center gap-1.5 rounded bg-quantum/90 px-3 py-1.5 text-xs font-semibold hover:bg-quantum disabled:opacity-60">
            <Sparkles size={13} /> {analyzing ? "Analyzing…" : "SentinelAI analysis"}
          </button>
        </div>
      </PageHeader>

      {incident.summary && <p className="mb-4 max-w-3xl text-sm text-ink-muted">{incident.summary}</p>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Timeline
          </h2>
          <ol className="relative ml-2 space-y-4 border-l border-line pl-5">
            {incident.events.map((e) => (
              <li key={e.id} className="relative">
                <span className="absolute -left-[26px] top-1 h-2.5 w-2.5 rounded-full border-2 border-midnight bg-orbital text-on-accent" />
                <p className="text-sm">{e.message}</p>
                <p className="telemetry !text-[11px] text-ink-faint">
                  {e.kind.toUpperCase()} · {timeAgo(e.at)}
                </p>
              </li>
            ))}
          </ol>
          <div className="mt-4 flex gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addNote()}
              placeholder="Add investigation note…"
              className="flex-1 rounded border border-line bg-navy px-3 py-2 text-sm" />
            <button onClick={addNote}
              className="rounded bg-orbital text-on-accent px-4 text-sm font-semibold hover:bg-orbital text-on-accent-deep">
              Log
            </button>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
              Linked alerts · Evidence
            </h2>
            {incident.alerts.length === 0 && (
              <p className="text-sm text-ink-muted">No alerts linked.</p>
            )}
            <ul className="space-y-2.5">
              {incident.alerts.map((a) => (
                <li key={a.id} className="flex items-start justify-between gap-2 text-sm">
                  <div>
                    <p>{a.title}</p>
                    <p className="text-xs text-ink-faint">{a.asset_name ?? "no asset"} · {a.source}</p>
                  </div>
                  <SeverityBadge value={a.severity} />
                </li>
              ))}
            </ul>
          </Card>

          {analysis && (
            <Card className="border-quantum/40">
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-quantum">
                <Sparkles size={13} /> SentinelAI analysis
              </h2>
              <p className="text-sm leading-relaxed text-ink-muted">{analysis.summary}</p>
              <h3 className="mt-3 text-xs font-semibold uppercase text-ink-faint">Root-cause hypotheses</h3>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-muted">
                {analysis.root_cause_hypotheses.map((h, i) => <li key={i}>{h}</li>)}
              </ul>
              <h3 className="mt-3 text-xs font-semibold uppercase text-ink-faint">Response plan</h3>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-ink-muted">
                {analysis.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
              <p className="telemetry mt-3 !text-[11px] text-ink-faint">via {analysis.provider}</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
