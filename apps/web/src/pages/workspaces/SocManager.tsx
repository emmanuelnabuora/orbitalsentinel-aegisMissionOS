import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, PageHeader, SeverityBadge, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { Alert, Incident, Page as P } from "@/lib/types";

export default function SocManager() {
  const [alerts, setAlerts] = useState<P<Alert> | null>(null);
  const [incidents, setIncidents] = useState<P<Incident> | null>(null);
  useEffect(() => {
    api.alerts("?limit=100").then(setAlerts).catch(() => undefined);
    api.incidents("?limit=8").then(setIncidents).catch(() => undefined);
  }, []);
  const bySev = (s: string) => alerts?.items.filter((a) => a.severity === s).length ?? 0;
  return (
    <div className="space-y-6">
      <PageHeader question="Is the SOC keeping pace with the threat picture?" title="SOC Command" />
      <div className="grid grid-cols-4 gap-4">
        <Stat label="Critical" value={String(bySev("critical"))} tone="text-critical" />
        <Stat label="High" value={String(bySev("high"))} tone="text-amber" />
        <Stat label="Medium" value={String(bySev("medium"))} />
        <Stat label="Open incidents" value={String(incidents?.total ?? "—")} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Active incidents</h3>
        <TableShell>
          <thead><tr><Th>Incident</Th><Th>Severity</Th><Th>Status</Th><Th>Opened</Th></tr></thead>
          <tbody>
            {(incidents?.items ?? []).map((i) => (
              <tr key={i.id} className="border-t border-line">
                <Td><Link to={`/investigations/${i.id}`} className="hover:text-orbital">{i.title}</Link></Td>
                <Td><SeverityBadge value={i.severity} /></Td>
                <Td>{i.status}</Td>
                <Td className="text-ink-muted">{timeAgo(i.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
