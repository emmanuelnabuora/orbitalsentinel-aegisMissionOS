import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Alert } from "@/lib/types";
import { PageHeader, SeverityBadge, StatusDot, TableShell, Td, Th, timeAgo } from "@/components/ui";

const SEVERITIES = ["", "critical", "high", "medium", "low", "info"];
const STATUSES = ["", "open", "acknowledged", "investigating", "resolved"];

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");

  const load = useCallback(() => {
    const q = new URLSearchParams({ limit: "100" });
    if (severity) q.set("severity", severity);
    if (status) q.set("status", status);
    api.alerts(`?${q}`).then((p) => setAlerts(p.items)).catch(() => undefined);
  }, [severity, status]);

  useEffect(load, [load]);

  async function advance(a: Alert) {
    const next = a.status === "open" ? "acknowledged"
      : a.status === "acknowledged" ? "investigating" : "resolved";
    await api.updateAlert(a.id, { status: next }).catch(() => undefined);
    load();
  }

  return (
    <div>
      <PageHeader question="What needs attention?" title="Alerts Center">
        <div className="flex gap-2">
          {[["Severity", severity, setSeverity, SEVERITIES] as const,
            ["Status", status, setStatus, STATUSES] as const].map(([label, val, set, opts]) => (
            <select key={label} value={val} onChange={(e) => set(e.target.value)}
              className="rounded border border-line bg-midnight px-2 py-1.5 text-sm capitalize">
              {opts.map((o) => <option key={o} value={o}>{o === "" ? `All ${label.toLowerCase()}` : o}</option>)}
            </select>
          ))}
        </div>
      </PageHeader>

      <TableShell>
        <thead>
          <tr><Th>Alert</Th><Th>Severity</Th><Th>Status</Th><Th>Asset</Th><Th>Source</Th>
            <Th>Age</Th><Th>Action</Th></tr>
        </thead>
        <tbody>
          {alerts.map((a) => (
            <tr key={a.id}>
              <Td className="max-w-md"><p className="truncate">{a.title}</p></Td>
              <Td><SeverityBadge value={a.severity} /></Td>
              <Td><StatusDot value={a.status} /></Td>
              <Td className="text-ink-muted">{a.asset_name ?? "—"}</Td>
              <Td className="telemetry !text-xs text-ink-faint">{a.source}</Td>
              <Td className="text-ink-faint">{timeAgo(a.created_at)}</Td>
              <Td>
                {a.status !== "resolved" && (
                  <button onClick={() => advance(a)}
                    className="rounded border border-line px-2 py-1 text-xs text-ink-muted hover:border-orbital hover:text-ink">
                    {a.status === "open" ? "Acknowledge"
                      : a.status === "acknowledged" ? "Investigate" : "Resolve"}
                  </button>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </TableShell>
      {alerts.length === 0 && (
        <p className="mt-4 text-sm text-ink-muted">No alerts match the current filters.</p>
      )}
    </div>
  );
}
