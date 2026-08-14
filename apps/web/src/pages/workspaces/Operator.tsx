import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, ClassificationBadge, PageHeader, SeverityBadge, Stat, TableShell, Td, Th } from "@/components/ui";
import type { Asset, FleetSummary, Page as P } from "@/lib/types";

export default function Operator() {
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [assets, setAssets] = useState<P<Asset> | null>(null);
  useEffect(() => {
    api.fleet().then(setFleet).catch(() => undefined);
    api.assets("?limit=8").then(setAssets).catch(() => undefined);
  }, []);
  const degraded = assets?.items.filter((a) => a.status !== "operational") ?? [];
  return (
    <div className="space-y-6">
      <PageHeader question="Is the fleet healthy enough to fly today's missions?" title="Mission Operations">
        <Link to="/ops" className="text-sm text-orbital hover:underline">Global operations →</Link>
      </PageHeader>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Missions tracked" value={String(fleet?.missions.length ?? "—")} />
        <Stat label="Assets" value={String(assets?.total ?? "—")} />
        <Stat label="Needing attention" value={String(degraded.length)}
          tone={degraded.length ? "text-amber" : "text-mission"} />
      </div>
      <Card>
        <h3 className="mb-3 text-sm font-semibold">Fleet status</h3>
        <TableShell>
          <thead><tr><Th>Asset</Th><Th>Type</Th><Th>Status</Th><Th>Criticality</Th></tr></thead>
          <tbody>
            {(assets?.items ?? []).map((a) => (
              <tr key={a.id} className="border-t border-line">
                <Td><span className="flex items-center gap-2"><Link to={`/assets/${a.id}`} className="hover:text-orbital">{a.name}</Link><ClassificationBadge value={a.classification} /></span></Td>
                <Td className="text-ink-muted">{a.asset_type.replace("_", " ")}</Td>
                <Td>{a.status}</Td>
                <Td><SeverityBadge value={a.criticality} /></Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
