import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, PageHeader, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { AuditEntry } from "@/lib/types";

export default function Auditor() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  useEffect(() => {
    api.auditLog(100).then(setEntries).catch(() => undefined);
  }, []);
  const accessEvents = entries.filter((e) =>
    e.action.startsWith("invite.") || e.action.startsWith("api_key.") || e.action.startsWith("workspace.")
  ).length;
  return (
    <div className="space-y-6">
      <PageHeader question="Who did what, and can we prove it?" title="Audit & Compliance" />
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Events (recent)" value={String(entries.length)} />
        <Stat label="Access changes" value={String(accessEvents)} />
        <Stat label="Last event" value={entries[0] ? timeAgo(entries[0].created_at) : "—"} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Audit trail</h3>
        <TableShell>
          <thead><tr><Th>Action</Th><Th>Resource</Th><Th>Actor</Th><Th>When</Th></tr></thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-t border-line">
                <Td><span className="telemetry">{e.action}</span></Td>
                <Td className="text-ink-muted">{e.resource_type ?? "—"}</Td>
                <Td className="telemetry text-ink-muted">{e.actor_id?.slice(0, 8) ?? "system"}</Td>
                <Td className="text-ink-muted">{timeAgo(e.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
