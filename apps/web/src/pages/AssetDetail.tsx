import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import type { Alert, Asset, CryptoRecord } from "@/lib/types";
import { Card, PageHeader, SeverityBadge, StatusDot, timeAgo } from "@/components/ui";

export default function AssetDetail() {
  const { id } = useParams();
  const [asset, setAsset] = useState<Asset | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [certs, setCerts] = useState<CryptoRecord[]>([]);

  useEffect(() => {
    if (!id) return;
    api.asset(id).then(setAsset).catch(() => undefined);
    api.alerts(`?asset_id=${id}&limit=20`).then((p) => setAlerts(p.items)).catch(() => undefined);
    api.quantumInventory(`?asset_id=${id}`).then((p) => setCerts(p.items)).catch(() => undefined);
  }, [id]);

  if (!asset) return <p className="text-sm text-ink-muted">Loading asset…</p>;
  const attrs = Object.entries(asset.attributes ?? {});

  return (
    <div>
      <PageHeader question="Is this asset healthy?" title={asset.name}>
        <div className="flex items-center gap-4 text-sm">
          <StatusDot value={asset.status} />
          <span className="capitalize text-ink-muted">{asset.criticality} criticality</span>
        </div>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Profile
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-faint">Type</dt>
              <dd className="capitalize">{asset.asset_type.replace("_", " ")}</dd>
            </div>
            {asset.description && (
              <div><dt className="text-ink-faint">Description</dt>
                <dd className="mt-1 text-ink-muted">{asset.description}</dd></div>
            )}
            {attrs.map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <dt className="capitalize text-ink-faint">{k.replace("_", " ")}</dt>
                <dd className="telemetry !text-sm">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Cryptography
          </h2>
          {certs.length === 0 && (
            <p className="text-sm text-ink-muted">No crypto records registered for this asset.</p>
          )}
          <ul className="space-y-2">
            {certs.map((c) => (
              <li key={c.id} className="flex items-center justify-between rounded border border-line bg-navy px-3 py-2 text-sm">
                <div>
                  <p className="telemetry !text-sm">
                    {c.algorithm}{c.key_size ? `-${c.key_size}` : ""}
                  </p>
                  <p className="text-xs capitalize text-ink-faint">{c.kind.replace("_", " ")}</p>
                </div>
                <span className={`text-xs font-semibold ${c.pqc_ready ? "text-mission" : "text-critical"}`}>
                  {c.pqc_ready ? "PQC READY" : "QUANTUM VULNERABLE"}
                </span>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            Threat history
          </h2>
          {alerts.length === 0 && <p className="text-sm text-ink-muted">No alerts recorded.</p>}
          <ul className="space-y-2.5">
            {alerts.map((a) => (
              <li key={a.id} className="flex items-start justify-between gap-2 text-sm">
                <div>
                  <p>{a.title}</p>
                  <p className="text-xs text-ink-faint">{a.source} · {timeAgo(a.created_at)}</p>
                </div>
                <SeverityBadge value={a.severity} />
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
