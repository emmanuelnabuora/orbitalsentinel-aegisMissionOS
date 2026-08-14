import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { PageHeader, StatusDot, TableShell, Td, Th, timeAgo } from "@/components/ui";

const TYPES = ["", "satellite", "ground_station", "orbital_datacenter", "network", "server",
  "application", "sensor"];

export default function Assets() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [total, setTotal] = useState(0);
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const q = new URLSearchParams({ limit: "100" });
    if (type) q.set("asset_type", type);
    if (search) q.set("search", search);
    const t = setTimeout(() => {
      api.assets(`?${q}`).then((p) => { setAssets(p.items); setTotal(p.total); })
        .catch(() => undefined);
    }, 200);
    return () => clearTimeout(t);
  }, [type, search]);

  return (
    <div>
      <PageHeader question="What are we protecting?" title="Asset Inventory">
        <div className="flex gap-2">
          <input placeholder="Search assets…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-56 rounded border border-line bg-midnight px-3 py-1.5 text-sm" />
          <select value={type} onChange={(e) => setType(e.target.value)}
            className="rounded border border-line bg-midnight px-2 py-1.5 text-sm">
            {TYPES.map((t) => (
              <option key={t} value={t}>{t === "" ? "All types" : t.replace("_", " ")}</option>
            ))}
          </select>
        </div>
      </PageHeader>

      <TableShell>
        <thead>
          <tr><Th>Name</Th><Th>Type</Th><Th>Status</Th><Th>Criticality</Th><Th>Updated</Th></tr>
        </thead>
        <tbody>
          {assets.map((a) => (
            <tr key={a.id}>
              <Td>
                <Link to={`/assets/${a.id}`} className="font-medium text-ink hover:text-orbital">
                  {a.name}
                </Link>
              </Td>
              <Td className="capitalize text-ink-muted">{a.asset_type.replace("_", " ")}</Td>
              <Td><StatusDot value={a.status} /></Td>
              <Td className="capitalize">{a.criticality}</Td>
              <Td className="text-ink-faint">{timeAgo(a.updated_at)}</Td>
            </tr>
          ))}
        </tbody>
      </TableShell>
      <p className="mt-2 text-xs text-ink-faint">{total} asset(s)</p>
    </div>
  );
}
