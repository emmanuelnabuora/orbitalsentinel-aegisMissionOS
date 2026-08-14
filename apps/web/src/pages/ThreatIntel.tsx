import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, RefreshCw, Zap } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ThreatIndicator, ThreatIntelSummary, ThreatMatch } from "@/lib/types";
import {
  Card, PageHeader, SeverityBadge, Stat, TableShell, Td, Th, timeAgo,
} from "@/components/ui";

export default function ThreatIntel() {
  const [summary, setSummary] = useState<ThreatIntelSummary | null>(null);
  const [indicators, setIndicators] = useState<ThreatIndicator[]>([]);
  const [matches, setMatches] = useState<ThreatMatch[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");

  const load = useCallback(() => {
    api.threatSummary().then(setSummary).catch(() => undefined);
    const q = new URLSearchParams({ limit: "200", active: "true" });
    if (typeFilter) q.set("indicator_type", typeFilter);
    api.threatIndicators(`?${q}`).then((p) => setIndicators(p.items)).catch(() => undefined);
    api.threatMatches().then(setMatches).catch(() => undefined);
  }, [typeFilter]);
  useEffect(load, [load]);

  async function run(kind: "ingest" | "correlate") {
    setBusy(kind); setError(null); setNotice(null);
    try {
      if (kind === "ingest") {
        const r = await api.threatIngest();
        const created = r.reduce((n, s) => n + s.created, 0);
        const updated = r.reduce((n, s) => n + s.updated, 0);
        setNotice(`Ingested ${r.length} feed(s): ${created} new, ${updated} refreshed.`);
      } else {
        const r = await api.threatCorrelate();
        setNotice(
          `Correlated ${r.indicators_checked} indicators against ${r.assets_checked} assets — ` +
          `${r.new_matches} new match(es), ${r.alerts_raised} alert(s) raised.`,
        );
      }
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Operation failed");
    } finally {
      setBusy(null);
    }
  }

  const sevTone = (s: string) =>
    s === "critical" ? "text-critical" : s === "high" ? "text-amber" : "text-ink";

  return (
    <div>
      <PageHeader question="Who is targeting us?" title="Threat Intelligence">
        <div className="flex gap-2">
          <button onClick={() => run("ingest")} disabled={busy !== null}
            className="flex items-center gap-1.5 rounded border border-line px-3 py-1.5 text-sm hover:border-orbital disabled:opacity-60">
            <RefreshCw size={14} className={busy === "ingest" ? "animate-spin" : ""} /> Ingest feeds
          </button>
          <button onClick={() => run("correlate")} disabled={busy !== null}
            className="flex items-center gap-1.5 rounded bg-orbital text-on-accent px-3 py-1.5 text-sm font-semibold hover:bg-orbital-deep disabled:opacity-60">
            <Zap size={14} /> Correlate fleet
          </button>
        </div>
      </PageHeader>

      {notice && <p className="mb-4 rounded border border-orbital/40 bg-orbital/10 px-3 py-2 text-sm">{notice}</p>}
      {error && <p className="mb-4 text-sm text-critical">{error}</p>}

      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Active Indicators" value={summary?.active_indicators ?? "—"}
          sub={summary ? `${Object.keys(summary.sources).length} source(s)` : undefined} />
        <Stat label="Asset Matches" value={summary?.total_matches ?? "—"}
          tone={summary && summary.total_matches > 0 ? "text-amber" : "text-mission"}
          sub="observed on our infrastructure" />
        <Stat label="Critical / High"
          value={summary ? (summary.by_severity.critical ?? 0) + (summary.by_severity.high ?? 0) : "—"}
          tone="text-critical" sub="severity indicators" />
        <Stat label="Last Ingest"
          value={summary?.last_ingest ? timeAgo(summary.last_ingest) : "never"} />
      </div>

      {summary && matches.length > 0 && (
        <Card className="mt-4 border-amber/40">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-amber">
            <Activity size={14} /> Indicators observed on our assets
          </h2>
          <TableShell>
            <thead>
              <tr><Th>Asset</Th><Th>Matched attribute</Th><Th>Indicator</Th>
                <Th>Category</Th><Th>Severity</Th><Th>Alert</Th><Th>When</Th></tr>
            </thead>
            <tbody>
              {matches.map((m) => (
                <tr key={m.id}>
                  <Td className="font-medium">{m.asset_name ?? "—"}</Td>
                  <Td className="telemetry !text-xs text-ink-muted">{m.matched_on}</Td>
                  <Td className="telemetry !text-xs">{m.indicator_value}</Td>
                  <Td className="capitalize text-ink-muted">{m.indicator_category}</Td>
                  <Td>{m.severity && <SeverityBadge value={m.severity} />}</Td>
                  <Td>
                    {m.alert_id
                      ? <Link to="/alerts" className="text-xs text-orbital hover:underline">view alert →</Link>
                      : <span className="text-xs text-ink-faint">—</span>}
                  </Td>
                  <Td className="text-ink-faint">{timeAgo(m.created_at)}</Td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Card>
      )}

      <div className="mb-2 mt-6 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-faint">
          Indicator feed
        </h2>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded border border-line bg-midnight px-2 py-1.5 text-sm">
          {["", "ip", "domain", "url", "file_hash", "email"].map((t) => (
            <option key={t} value={t}>{t === "" ? "All types" : t.replace("_", " ")}</option>
          ))}
        </select>
      </div>
      <TableShell>
        <thead>
          <tr><Th>Indicator</Th><Th>Type</Th><Th>Category</Th><Th>Severity</Th>
            <Th>Confidence</Th><Th>Source</Th><Th>Last seen</Th></tr>
        </thead>
        <tbody>
          {indicators.map((i) => (
            <tr key={i.id}>
              <Td className="telemetry !text-xs">{i.value}</Td>
              <Td className="uppercase text-ink-muted">{i.indicator_type.replace("_", " ")}</Td>
              <Td className="capitalize">{i.category}</Td>
              <Td><SeverityBadge value={i.severity} /></Td>
              <Td className={`telemetry !text-sm ${sevTone(i.severity)}`}>{i.confidence}</Td>
              <Td className="text-ink-faint">{i.source}</Td>
              <Td className="text-ink-faint">{timeAgo(i.last_seen)}</Td>
            </tr>
          ))}
        </tbody>
      </TableShell>
      {indicators.length === 0 && (
        <p className="mt-4 text-sm text-ink-muted">
          No indicators yet. Click <span className="text-ink">Ingest feeds</span> to pull the
          curated threat feed, then <span className="text-ink">Correlate fleet</span> to match
          against your assets.
        </p>
      )}
    </div>
  );
}
