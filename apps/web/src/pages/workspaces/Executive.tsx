import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, PageHeader, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { FleetSummary, Page as P, Report } from "@/lib/types";

export default function Executive() {
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [reports, setReports] = useState<P<Report> | null>(null);
  useEffect(() => {
    api.fleet().then(setFleet).catch(() => undefined);
    api.reports("?limit=6").then(setReports).catch(() => undefined);
  }, []);
  return (
    <div className="space-y-6">
      <PageHeader question="Is the mission assured?" title="Executive Overview">
        <Link to="/reports" className="text-sm text-orbital hover:underline">All reports →</Link>
      </PageHeader>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Missions" value={String(fleet?.missions.length ?? "—")} />
        <Stat label="Fleet assurance" value={fleet ? `${Math.round(fleet.average_score)}%` : "—"}
          tone={fleet && fleet.average_score >= 80 ? "text-mission" : "text-amber"} />
        <Stat label="Reports this period" value={String(reports?.total ?? "—")} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Latest reporting</h3>
        <TableShell>
          <thead><tr><Th>Report</Th><Th>Kind</Th><Th>Generated</Th></tr></thead>
          <tbody>
            {(reports?.items ?? []).map((r) => (
              <tr key={r.id} className="border-t border-line">
                <Td><Link to="/reports" className="hover:text-orbital">{r.title}</Link></Td>
                <Td className="text-ink-muted">{r.kind}</Td>
                <Td className="text-ink-muted">{timeAgo(r.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
