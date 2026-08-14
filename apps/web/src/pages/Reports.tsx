import { useCallback, useEffect, useState } from "react";
import { Download, FileText, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Incident, Report, ReportDetail } from "@/lib/types";
import {
  Card, PageHeader, TableShell, Td, Th, timeAgo,
} from "@/components/ui";

const KINDS = [
  { value: "executive", label: "Executive Summary" },
  { value: "mission_assurance", label: "Mission Assurance" },
  { value: "threat_intel", label: "Threat Intelligence" },
  { value: "quantum_readiness", label: "Quantum Readiness" },
  { value: "incident", label: "Incident" },
];

export default function Reports() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selected, setSelected] = useState<ReportDetail | null>(null);
  const [kind, setKind] = useState("executive");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.reports("?limit=100").then((p) => setReports(p.items)).catch(() => undefined);
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    if (kind === "incident") {
      api.incidents("?limit=100").then((p) => setIncidents(p.items)).catch(() => undefined);
    }
  }, [kind]);

  async function generate() {
    setBusy(true); setError(null);
    try {
      const report = await api.generateReport(
        kind, kind === "incident" ? subjectId || undefined : undefined,
      );
      setSelected(report);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function open(id: string) {
    setSelected(await api.report(id).catch(() => null));
  }

  async function download(r: Report) {
    await api.downloadReportPdf(r.id, `aegis-${r.kind}-${r.created_at.slice(0, 10)}.pdf`)
      .catch(() => setError("Export failed"));
  }

  return (
    <div>
      <PageHeader question="What do we tell leadership?" title="Reports" />

      <Card className="mb-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
          Generate a report
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-ink-faint">Type</label>
            <select value={kind} onChange={(e) => setKind(e.target.value)}
              className="rounded border border-line bg-navy px-3 py-2 text-sm">
              {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
          </div>
          {kind === "incident" && (
            <div>
              <label className="mb-1 block text-xs text-ink-faint">Incident</label>
              <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}
                className="rounded border border-line bg-navy px-3 py-2 text-sm">
                <option value="">Select incident…</option>
                {incidents.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
              </select>
            </div>
          )}
          <button onClick={generate} disabled={busy || (kind === "incident" && !subjectId)}
            className="flex items-center gap-1.5 rounded bg-orbital text-on-accent px-4 py-2 text-sm font-semibold hover:bg-orbital-deep disabled:opacity-60">
            <Plus size={15} /> {busy ? "Generating…" : "Generate"}
          </button>
          {error && <span className="text-sm text-critical">{error}</span>}
        </div>
        <p className="mt-3 text-xs text-ink-faint">
          Reports are immutable snapshots built from live data at generation time,
          with the narrative written by SentinelAI.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Report history
          </h2>
          <TableShell>
            <thead>
              <tr><Th>Report</Th><Th>Type</Th><Th>Generated</Th><Th>Export</Th></tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="cursor-pointer" onClick={() => open(r.id)}>
                  <Td className="font-medium text-ink">{r.title}</Td>
                  <Td className="capitalize text-ink-muted">{r.kind.replace("_", " ")}</Td>
                  <Td className="text-ink-faint">{timeAgo(r.created_at)}</Td>
                  <Td>
                    <button onClick={(e) => { e.stopPropagation(); download(r); }}
                      className="flex items-center gap-1 text-xs text-orbital hover:underline">
                      <Download size={13} /> PDF
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableShell>
          {reports.length === 0 && (
            <p className="mt-4 text-sm text-ink-muted">
              No reports yet. Generate one above.
            </p>
          )}
        </div>

        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Preview
          </h2>
          {selected ? (
            <Card>
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-orbital">
                    {selected.kind.replace("_", " ")}
                  </p>
                  <h3 className="text-lg font-bold">{selected.title}</h3>
                  <p className="telemetry !text-[11px] text-ink-faint">
                    {new Date(selected.created_at).toISOString().slice(0, 16).replace("T", " ")} UTC
                    · via {selected.provider}
                  </p>
                </div>
                <button onClick={() => download(selected)}
                  className="flex shrink-0 items-center gap-1.5 rounded border border-line px-3 py-1.5 text-xs hover:border-orbital">
                  <Download size={13} /> Export PDF
                </button>
              </div>
              <p className="text-sm leading-relaxed text-ink-muted">{selected.content.summary}</p>
              {selected.content.sections.map((sec, i) => (
                <div key={i} className="mt-4">
                  <h4 className="text-sm font-semibold">{sec.heading}</h4>
                  {sec.body && <p className="mt-1 text-sm text-ink-muted">{sec.body}</p>}
                  {sec.rows && sec.rows.length > 0 && (
                    <table className="mt-2 w-full border-collapse text-xs">
                      {sec.columns && (
                        <thead>
                          <tr>{sec.columns.map((c) => (
                            <th key={c} className="border border-line bg-navy px-2 py-1 text-left text-[10px] uppercase text-ink-faint">{c}</th>
                          ))}</tr>
                        </thead>
                      )}
                      <tbody>
                        {sec.rows.map((row, ri) => (
                          <tr key={ri}>{row.map((cell, ci) => (
                            <td key={ci} className="border border-line px-2 py-1 text-ink-muted">{cell}</td>
                          ))}</tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ))}
            </Card>
          ) : (
            <Card className="py-12 text-center">
              <FileText className="mx-auto text-ink-faint" size={22} />
              <p className="mt-3 text-sm text-ink-muted">
                Select a report to preview, or generate a new one.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
