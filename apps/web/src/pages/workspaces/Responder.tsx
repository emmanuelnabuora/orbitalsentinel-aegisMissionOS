import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, PageHeader, SeverityBadge, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { Incident, Page as P } from "@/lib/types";

export default function Responder() {
  const [incidents, setIncidents] = useState<P<Incident> | null>(null);
  useEffect(() => {
    api.incidents("?limit=10").then(setIncidents).catch(() => undefined);
  }, []);
  const active = incidents?.items.filter((i) => i.status !== "closed") ?? [];
  const contained = incidents?.items.filter((i) => i.status === "contained").length ?? 0;
  return (
    <div className="space-y-6">
      <PageHeader question="What needs containing, and what's the next action?" title="Incident Response">
        <Link to="/investigations" className="text-sm text-orbital hover:underline">All investigations →</Link>
      </PageHeader>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Active cases" value={String(active.length)}
          tone={active.length ? "text-amber" : "text-mission"} />
        <Stat label="Contained" value={String(contained)} tone="text-mission" />
        <Stat label="Oldest open" value={active.length ? timeAgo(active[active.length - 1]!.created_at) : "—"} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Response queue</h3>
        <TableShell>
          <thead><tr><Th>Case</Th><Th>Severity</Th><Th>Status</Th><Th>Opened</Th></tr></thead>
          <tbody>
            {active.map((i) => (
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
