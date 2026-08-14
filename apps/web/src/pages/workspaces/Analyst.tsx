import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, ClassificationBadge, PageHeader, SeverityBadge, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { Alert, Page as P } from "@/lib/types";

export default function Analyst() {
  const [alerts, setAlerts] = useState<P<Alert> | null>(null);
  useEffect(() => {
    api.alerts("?limit=10&status=open").then(setAlerts).catch(() => undefined);
  }, []);
  const critical = alerts?.items.filter((a) => a.severity === "critical").length ?? 0;
  return (
    <div className="space-y-6">
      <PageHeader question="What needs investigating right now?" title="Security Analysis">
        <Link to="/threat-intel" className="text-sm text-orbital hover:underline">Threat intelligence →</Link>
      </PageHeader>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Open alerts" value={String(alerts?.total ?? "—")} />
        <Stat label="Critical" value={String(critical)} tone={critical ? "text-critical" : "text-mission"} />
        <Stat label="Queue age" value={alerts?.items[0] ? timeAgo(alerts.items[0].created_at) : "—"} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Triage queue</h3>
        <TableShell>
          <thead><tr><Th>Alert</Th><Th>Severity</Th><Th>Source</Th><Th>Age</Th></tr></thead>
          <tbody>
            {(alerts?.items ?? []).map((a) => (
              <tr key={a.id} className="border-t border-line">
                <Td><span className="flex items-center gap-2"><Link to="/alerts" className="hover:text-orbital">{a.title}</Link><ClassificationBadge value={a.classification} /></span></Td>
                <Td><SeverityBadge value={a.severity} /></Td>
                <Td className="telemetry text-ink-muted">{a.source}</Td>
                <Td className="text-ink-muted">{timeAgo(a.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
