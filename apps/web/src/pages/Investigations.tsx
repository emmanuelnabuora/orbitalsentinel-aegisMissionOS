import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { Incident } from "@/lib/types";
import { PageHeader, SeverityBadge, StatusDot, TableShell, Td, Th, timeAgo } from "@/components/ui";

export default function Investigations() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  useEffect(() => {
    api.incidents("?limit=100").then((p) => setIncidents(p.items)).catch(() => undefined);
  }, []);

  return (
    <div>
      <PageHeader question="What happened?" title="Incident Investigations" />
      <TableShell>
        <thead>
          <tr><Th>Incident</Th><Th>Severity</Th><Th>Status</Th><Th>Opened</Th></tr>
        </thead>
        <tbody>
          {incidents.map((i) => (
            <tr key={i.id}>
              <Td>
                <Link to={`/investigations/${i.id}`}
                  className="font-medium text-ink hover:text-orbital">{i.title}</Link>
              </Td>
              <Td><SeverityBadge value={i.severity} /></Td>
              <Td><StatusDot value={i.status} /></Td>
              <Td className="text-ink-faint">{timeAgo(i.created_at)}</Td>
            </tr>
          ))}
        </tbody>
      </TableShell>
      {incidents.length === 0 && (
        <p className="mt-4 text-sm text-ink-muted">No incidents open. Stay ready.</p>
      )}
    </div>
  );
}
