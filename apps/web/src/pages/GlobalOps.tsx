import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { Card, PageHeader, StatusDot } from "@/components/ui";

const FILL: Record<string, string> = {
  operational: "#10B981", degraded: "#F59E0B", offline: "#EF4444", unknown: "#64748B",
};

function coords(a: Asset): { lat: number; lon: number } | null {
  const lat = Number(a.attributes?.lat); const lon = Number(a.attributes?.lon);
  return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
}

export default function GlobalOps() {
  const [assets, setAssets] = useState<Asset[]>([]);
  useEffect(() => {
    api.assets("?limit=100").then((p) => setAssets(p.items)).catch(() => undefined);
  }, []);

  const W = 900; const H = 450;
  const project = (lat: number, lon: number) => ({
    x: ((lon + 180) / 360) * W,
    y: ((90 - lat) / 180) * H,
  });
  const located = assets.map((a) => ({ asset: a, c: coords(a) }))
    .filter((e): e is { asset: Asset; c: { lat: number; lon: number } } => e.c !== null);

  return (
    <div>
      <PageHeader question="Where is everything, right now?" title="Global Operations Center" />
      <Card className="!p-0">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
          <rect width={W} height={H} fill="#0B1220" />
          {/* graticule */}
          {Array.from({ length: 17 }, (_, i) => (i + 1) * 50).map((x) => (
            <line key={`v${x}`} x1={x} y1={0} x2={x} y2={H} stroke="#1F2A44" strokeWidth={0.5} />
          ))}
          {Array.from({ length: 8 }, (_, i) => (i + 1) * 50).map((y) => (
            <line key={`h${y}`} x1={0} y1={y} x2={W} y2={y} stroke="#1F2A44" strokeWidth={0.5} />
          ))}
          <line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke="#243154" strokeWidth={1} />
          {located.map(({ asset, c }) => {
            const p = project(c.lat, c.lon);
            const sat = asset.asset_type === "satellite";
            return (
              <g key={asset.id}>
                {sat && (
                  <circle cx={p.x} cy={p.y} r={14} fill="none"
                    stroke={FILL[asset.status] ?? "#64748B"} strokeWidth={0.75} opacity={0.5} />
                )}
                <circle cx={p.x} cy={p.y} r={sat ? 5 : 4}
                  fill={FILL[asset.status] ?? "#64748B"} />
                <text x={p.x + 10} y={p.y + 4} fill="#9CA3AF" fontSize={10}
                  fontFamily="JetBrains Mono, monospace">{asset.name}</text>
              </g>
            );
          })}
        </svg>
      </Card>
      <div className="mt-2 flex gap-5 text-xs text-ink-muted">
        {Object.entries(FILL).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1.5 capitalize">
            <span className="h-2 w-2 rounded-full" style={{ background: v }} /> {k}
          </span>
        ))}
      </div>

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wider text-ink-faint">
        Tracked assets
      </h2>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {assets.map((a) => {
          const c = coords(a);
          return (
            <Link key={a.id} to={`/assets/${a.id}`}
              className="rounded border border-line bg-midnight p-3 hover:border-orbital/60">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{a.name}</span>
                <StatusDot value={a.status} />
              </div>
              <p className="telemetry mt-1 !text-xs text-ink-faint">
                {c ? `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}` : "no position data"} ·{" "}
                {a.asset_type.replace("_", " ")}
              </p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
