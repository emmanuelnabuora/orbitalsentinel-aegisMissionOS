import { useEffect, useState } from "react";
import { AlertTriangle, FlaskConical, Play, Plus, Save, Trash2, TrendingDown, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Asset, Perturbation, Scenario, SimulationResult } from "@/lib/types";
import { Card, PageHeader, ScoreBar, Stat, TableShell, Td, Th } from "@/components/ui";

const KIND_LABEL: Record<string, string> = {
  offline: "Force offline",
  set_status: "Set status",
  add_alerts: "Inject alerts",
  remove_asset: "Remove from fleet",
};

export default function DigitalTwin() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [name, setName] = useState("Untitled scenario");
  const [perturbations, setPerturbations] = useState<Perturbation[]>([]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // draft row
  const [dAsset, setDAsset] = useState("");
  const [dKind, setDKind] = useState<Perturbation["kind"]>("offline");
  const [dStatus, setDStatus] = useState("degraded");
  const [dMag, setDMag] = useState(1);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);

  const loadScenarios = () =>
    api.listScenarios().then(setScenarios).catch(() => undefined);

  useEffect(() => {
    api.assets("?limit=200").then((p) => {
      setAssets(p.items);
      if (p.items[0]) setDAsset(p.items[0].id);
    }).catch(() => undefined);
    loadScenarios();
  }, []);

  async function saveScenario() {
    if (perturbations.length === 0) return;
    setBusy(true); setError(null);
    try {
      await api.createScenario(name, null, perturbations);
      loadScenarios();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function runSaved(s: Scenario) {
    setBusy(true); setError(null); setName(s.name);
    try {
      setResult(await api.runScenario(s.id));
      loadScenarios();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeScenario(id: string) {
    await api.deleteScenario(id).catch(() => undefined);
    loadScenarios();
  }

  const assetName = (id: string) => assets.find((a) => a.id === id)?.name ?? id.slice(0, 8);

  function addPerturbation() {
    if (!dAsset) return;
    const p: Perturbation = { kind: dKind, asset_id: dAsset };
    if (dKind === "set_status") p.status = dStatus;
    if (dKind === "add_alerts") p.magnitude = dMag;
    setPerturbations((list) => [...list, p]);
  }

  function removePerturbation(i: number) {
    setPerturbations((list) => list.filter((_, idx) => idx !== i));
  }

  async function run() {
    if (perturbations.length === 0) return;
    setBusy(true); setError(null);
    try {
      setResult(await api.simulate(name, perturbations));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Simulation failed");
    } finally {
      setBusy(false);
    }
  }

  const deltaTone = (d: number) =>
    d < 0 ? "text-critical" : d > 0 ? "text-mission" : "text-ink-muted";
  const healthTone = (h: string) =>
    h === "assured" ? "text-mission" : h === "degraded" ? "text-amber" : "text-critical";

  return (
    <div>
      <PageHeader question="What if this fails?" title="Digital Twin" />

      <div className="grid gap-4 lg:grid-cols-5">
        {/* Scenario builder */}
        <Card className="lg:col-span-2">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            <FlaskConical size={14} /> Scenario
          </h2>
          <input value={name} onChange={(e) => setName(e.target.value)}
            className="mb-3 w-full rounded border border-line bg-navy px-3 py-2 text-sm"
            placeholder="Scenario name" />

          <div className="space-y-2 rounded border border-line bg-navy p-3">
            <select value={dAsset} onChange={(e) => setDAsset(e.target.value)}
              className="w-full rounded border border-line bg-midnight px-2 py-1.5 text-sm">
              {assets.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <div className="flex gap-2">
              <select value={dKind} onChange={(e) => setDKind(e.target.value as Perturbation["kind"])}
                className="flex-1 rounded border border-line bg-midnight px-2 py-1.5 text-sm">
                {Object.entries(KIND_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              {dKind === "set_status" && (
                <select value={dStatus} onChange={(e) => setDStatus(e.target.value)}
                  className="rounded border border-line bg-midnight px-2 py-1.5 text-sm">
                  {["degraded", "offline", "unknown", "operational"].map((s) =>
                    <option key={s} value={s}>{s}</option>)}
                </select>
              )}
              {dKind === "add_alerts" && (
                <input type="number" min={1} max={20} value={dMag}
                  onChange={(e) => setDMag(Number(e.target.value))}
                  className="w-20 rounded border border-line bg-midnight px-2 py-1.5 text-sm" />
              )}
            </div>
            <button onClick={addPerturbation}
              className="flex w-full items-center justify-center gap-1.5 rounded border border-line py-1.5 text-sm hover:border-orbital">
              <Plus size={14} /> Add perturbation
            </button>
          </div>

          {perturbations.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {perturbations.map((p, i) => (
                <li key={i} className="flex items-center justify-between rounded bg-raised px-3 py-1.5 text-sm">
                  <span>
                    <span className="text-ink-muted">{KIND_LABEL[p.kind]}</span>{" "}
                    <span className="font-medium">{assetName(p.asset_id)}</span>
                    {p.status && <span className="text-ink-faint"> → {p.status}</span>}
                    {p.magnitude != null && p.kind === "add_alerts" &&
                      <span className="text-ink-faint"> ×{p.magnitude}</span>}
                  </span>
                  <button onClick={() => removePerturbation(i)}
                    className="text-ink-faint hover:text-critical"><X size={14} /></button>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-4 flex gap-2">
            <button onClick={run} disabled={busy || perturbations.length === 0}
              className="flex-1 rounded bg-orbital text-on-accent py-2.5 text-sm font-semibold hover:bg-orbital-deep disabled:opacity-60">
              {busy ? "Simulating…" : "Run simulation"}
            </button>
            <button onClick={saveScenario} disabled={busy || perturbations.length === 0}
              title="Save to scenario library"
              className="flex items-center gap-1.5 rounded border border-line px-3 text-sm hover:border-orbital disabled:opacity-60">
              <Save size={14} /> Save
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-critical">{error}</p>}
          <p className="mt-3 text-xs text-ink-faint">
            Simulations are read-only projections. Real assets, alerts, and scores are never modified.
          </p>

          {scenarios.length > 0 && (
            <div className="mt-4 border-t border-line pt-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                Scenario library
              </h3>
              <ul className="space-y-1.5">
                {scenarios.map((s) => (
                  <li key={s.id}
                    className="flex items-center justify-between gap-2 rounded border border-line bg-navy px-3 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm">{s.name}</p>
                      <p className="text-[11px] text-ink-faint">
                        {s.perturbations.length} perturbation(s)
                        {s.last_run_at ? " · run before" : " · never run"}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button onClick={() => runSaved(s)} disabled={busy}
                        title="Run scenario"
                        className="rounded border border-line p-1.5 text-ink-muted hover:border-orbital hover:text-ink disabled:opacity-60">
                        <Play size={13} />
                      </button>
                      <button onClick={() => removeScenario(s.id)}
                        title="Delete scenario"
                        className="rounded border border-line p-1.5 text-ink-muted hover:border-critical hover:text-critical">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* Results */}
        <div className="lg:col-span-3">
          {!result ? (
            <Card className="flex h-full items-center justify-center py-16 text-center">
              <div>
                <FlaskConical className="mx-auto text-ink-faint" size={24} />
                <p className="mt-3 text-sm text-ink-muted">
                  Build a scenario and run it to project fleet impact.
                </p>
              </div>
            </Card>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <Stat label="Baseline Assurance" value={result.baseline_average} />
                <Stat label="Projected Assurance" value={result.projected_average}
                  tone={result.projected_average >= 80 ? "text-mission"
                    : result.projected_average >= 50 ? "text-amber" : "text-critical"}
                  sub={`${result.average_delta >= 0 ? "+" : ""}${result.average_delta} vs baseline`} />
                <Stat label="Missions At Risk"
                  value={`${result.missions_at_risk_before} → ${result.missions_at_risk_after}`}
                  tone={result.missions_at_risk_after > result.missions_at_risk_before
                    ? "text-critical" : "text-mission"} />
              </div>

              <Card className={result.newly_at_risk.length ? "border-critical/40" : ""}>
                <div className="flex items-start gap-2">
                  {result.newly_at_risk.length > 0
                    ? <AlertTriangle className="mt-0.5 shrink-0 text-critical" size={16} />
                    : <TrendingDown className="mt-0.5 shrink-0 text-ink-faint" size={16} />}
                  <p className="text-sm leading-relaxed text-ink-muted">{result.summary}</p>
                </div>
              </Card>

              <Card>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
                  Mission impact
                </h3>
                <TableShell>
                  <thead>
                    <tr><Th>Mission</Th><Th>Baseline</Th><Th>Projected</Th>
                      <Th>Δ</Th><Th>Health</Th></tr>
                  </thead>
                  <tbody>
                    {result.missions.map((m) => (
                      <tr key={m.mission_id}>
                        <Td className="font-medium">{m.name}</Td>
                        <Td className="telemetry !text-sm">{m.baseline_score}</Td>
                        <Td>
                          <span className="telemetry !text-sm">{m.projected_score}</span>
                          <span className="mt-1 block w-20"><ScoreBar score={m.projected_score} /></span>
                        </Td>
                        <Td className={`telemetry !text-sm font-medium ${deltaTone(m.delta)}`}>
                          {m.delta >= 0 ? "+" : ""}{m.delta}
                        </Td>
                        <Td>
                          <span className={`capitalize ${healthTone(m.projected_health)}`}>
                            {m.projected_health.replace("_", " ")}
                          </span>
                          {m.crossed_threshold && (
                            <span className="ml-1 text-[10px] uppercase text-amber">changed</span>
                          )}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </TableShell>
              </Card>

              {result.impacted_assets.length > 0 && (
                <Card>
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-faint">
                    Impacted assets
                  </h3>
                  <ul className="space-y-1.5 text-sm">
                    {result.impacted_assets.map((a) => (
                      <li key={a.asset_id} className="flex items-center justify-between">
                        <span className="font-medium">{a.name}</span>
                        <span className="telemetry !text-xs text-ink-muted">
                          {a.removed
                            ? "removed from fleet"
                            : a.added_alerts > 0
                              ? `+${a.added_alerts} alert(s)`
                              : `${a.baseline_status} → ${a.projected_status}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
