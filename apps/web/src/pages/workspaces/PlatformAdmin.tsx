import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, PageHeader, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { Page as P, User, Workspace } from "@/lib/types";

export default function PlatformAdmin() {
  const [users, setUsers] = useState<P<User> | null>(null);
  const [spaces, setSpaces] = useState<Workspace[]>([]);
  useEffect(() => {
    api.users("?limit=100").then(setUsers).catch(() => undefined);
    api.workspaces().then(setSpaces).catch(() => undefined);
  }, []);
  const svc = users?.items.filter((u) => (u as User & { is_service_account?: boolean }).is_service_account).length ?? 0;
  return (
    <div className="space-y-6">
      <PageHeader question="Who has access to the platform, and where?" title="Platform Administration">
        <Link to="/admin" className="text-sm text-orbital hover:underline">User management →</Link>
      </PageHeader>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Users" value={String(users?.total ?? "—")} />
        <Stat label="Workspaces" value={String(spaces.length)} />
        <Stat label="Service accounts" value={String(svc)} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Workspaces</h3>
        <TableShell>
          <thead><tr><Th>Name</Th><Th>Slug</Th><Th>Created</Th></tr></thead>
          <tbody>
            {spaces.map((w) => (
              <tr key={w.id} className="border-t border-line">
                <Td>{w.name}</Td>
                <Td><span className="telemetry">{w.slug}</span></Td>
                <Td className="text-ink-muted">{timeAgo(w.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
