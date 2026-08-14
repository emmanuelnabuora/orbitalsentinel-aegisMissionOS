import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CryptoRecord, QuantumReadiness } from "@/lib/types";
import { Card, PageHeader, Stat, TableShell, Td, Th } from "@/components/ui";

export default function Quantum() {
  const [readiness, setReadiness] = useState<QuantumReadiness | null>(null);
  const [records, setRecords] = useState<CryptoRecord[]>([]);

  useEffect(() => {
    api.quantumReadiness().then(setReadiness).catch(() => undefined);
    api.quantumInventory("?limit=200").then((p) => setRecords(p.items)).catch(() => undefined);
  }, []);

  const tone = readiness
    ? readiness.score >= 80 ? "text-mission" : readiness.score >= 50 ? "text-amber" : "text-critical"
    : undefined;

  return (
    <div>
      <PageHeader question="Are we ready for quantum threats?" title="QuantumShield" />
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="PQC Readiness" value={readiness ? readiness.score : "—"} tone={tone}
          sub={readiness ? `${readiness.pqc_ready_records}/${readiness.total_records} records quantum-resistant` : undefined} />
        <Stat label="Vulnerable Records" value={readiness ? readiness.vulnerable_records : "—"}
          tone={readiness && readiness.vulnerable_records > 0 ? "text-critical" : "text-mission"}
          sub={readiness ? Object.entries(readiness.vulnerable_by_algorithm)
            .map(([k, v]) => `${k}×${v}`).join(" · ") || "none" : undefined} />
        <Stat label="Exposed Assets" value={readiness ? readiness.exposed_assets.length : "—"}
          tone={readiness && readiness.exposed_assets.length > 0 ? "text-amber" : "text-mission"}
          sub={readiness?.exposed_assets.join(", ") || undefined} />
      </div>

      {readiness && (
        <Card className="mt-4 border-quantum/40">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-quantum">
            Migration planner
          </h2>
          <ol className="list-decimal space-y-1.5 pl-5 text-sm text-ink-muted">
            {readiness.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ol>
        </Card>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wider text-ink-faint">
        Crypto inventory
      </h2>
      <TableShell>
        <thead>
          <tr><Th>Asset</Th><Th>Kind</Th><Th>Algorithm</Th><Th>Key size</Th>
            <Th>Subject</Th><Th>PQC status</Th></tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id}>
              <Td>{r.asset_name ?? "—"}</Td>
              <Td className="capitalize text-ink-muted">{r.kind.replace("_", " ")}</Td>
              <Td className="telemetry !text-sm">{r.algorithm}</Td>
              <Td className="telemetry !text-sm text-ink-muted">{r.key_size ?? "—"}</Td>
              <Td className="text-ink-muted">{r.subject ?? "—"}</Td>
              <Td>
                <span className={`text-xs font-semibold ${r.pqc_ready ? "text-mission" : "text-critical"}`}>
                  {r.pqc_ready ? "READY" : "VULNERABLE"}
                </span>
              </Td>
            </tr>
          ))}
        </tbody>
      </TableShell>
    </div>
  );
}
