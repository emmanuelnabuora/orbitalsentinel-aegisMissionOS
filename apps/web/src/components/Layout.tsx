import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity, Bell, Boxes, FileText, FlaskConical, Globe2, LayoutDashboard, LogOut, Network,
  Radar, Settings, ShieldCheck, Sparkles,
} from "lucide-react";
import { api, setSessionExpiredHandler } from "@/lib/api";
import type { FleetSummary, User, Workspace } from "@/lib/types";
import { personaFor, canSee, type PersonaDef } from "@/lib/workspaces";
import { activeWorkspace, setActiveWorkspace } from "@/lib/workspaceContext";
import { ScoreBar } from "./ui";
import NotificationBell from "./NotificationBell";
import { Moon, Sun } from "lucide-react";
import { applyTheme, currentTheme, type Theme } from "@/lib/theme";

const NAV = [
  { to: "/", label: "My Workspace", icon: LayoutDashboard, end: true },
  { to: "/ops", label: "Global Operations", icon: Globe2 },
  { to: "/assets", label: "Assets", icon: Boxes },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/investigations", label: "Investigations", icon: Radar },
  { to: "/threat-intel", label: "Threat Intelligence", icon: Activity },
  { to: "/missioniq", label: "MissionIQ", icon: Network },
  { to: "/digital-twin", label: "Digital Twin", icon: FlaskConical },
  { to: "/quantumshield", label: "QuantumShield", icon: ShieldCheck },
  { to: "/sentinel", label: "SentinelAI", icon: Sparkles },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/admin", label: "Administration", icon: Settings },
];

export default function Layout() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [fleet, setFleet] = useState<FleetSummary | null>(null);
  const [persona, setPersona] = useState<PersonaDef | null>(null);
  const [spaces, setSpaces] = useState<Workspace[]>([]);
  const [ws, setWs] = useState<string | null>(activeWorkspace());
  const [theme, setTheme] = useState<Theme>(currentTheme());

  useEffect(() => {
    setSessionExpiredHandler(() => navigate("/login"));
    api.me().then((u) => { setUser(u); setPersona(personaFor(u.roles)); }).catch(() => navigate("/login"));
    api.workspaces().then(setSpaces).catch(() => undefined);
    const onWs = () => setWs(activeWorkspace());
    window.addEventListener("aegis:workspace", onWs);
    return () => window.removeEventListener("aegis:workspace", onWs);
  }, [navigate]);

  useEffect(() => {
    // Auto-select the sole workspace so tenancy scoping applies by default.
    const only = spaces[0];
    if (!ws && spaces.length === 1 && only) setActiveWorkspace(only.slug);
  }, [ws, spaces]);

  useEffect(() => {
    const load = () => api.fleet().then(setFleet).catch(() => undefined);
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []);

  const threatTone: Record<string, string> = {
    low: "text-mission", elevated: "text-amber", high: "text-amber", severe: "text-critical",
  };

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="skip-link">Skip to main content</a>
      <aside className="fixed inset-y-0 w-[220px] border-r border-line bg-midnight">
        <div className="flex h-14 items-center gap-2 border-b border-line px-4">
          <img src="/brand/shield.png" alt="" className="h-8 w-8 rounded object-cover" />
          <div className="leading-tight">
            <p className="text-sm font-bold tracking-wide">AEGIS</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-ink-faint">MissionOS</p>
          </div>
        </div>
        {persona && (
          <div className="border-b border-line px-4 py-2">
            <p className="text-[10px] uppercase tracking-[0.2em] text-orbital">{persona.eyebrow}</p>
          </div>
        )}
        <nav className="space-y-0.5 p-2">
          {NAV.filter(({ to }) => !persona || to === "/" || canSee(persona, to)).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded px-3 py-2 text-sm transition-colors ${
                  isActive ? "bg-orbital/15 text-ink font-medium border-l-2 border-orbital -ml-[2px]"
                           : "text-ink-muted hover:bg-raised hover:text-ink"}`}>
              <Icon size={15} strokeWidth={1.75} /> {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="ml-[220px] flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-line bg-midnight px-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => { const next: Theme = theme === "dark" ? "light" : "dark"; applyTheme(next); setTheme(next); }}
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              className="rounded p-2 text-ink-muted hover:bg-raised hover:text-ink"
            >
              {theme === "dark" ? <Sun size={16} strokeWidth={1.75} /> : <Moon size={16} strokeWidth={1.75} />}
            </button>
            <NotificationBell />
            {spaces.length > 0 && (
              <select
                value={ws ?? ""}
                onChange={(e) => setActiveWorkspace(e.target.value || null)}
                aria-label="Active workspace"
                className="rounded border border-line bg-navy px-2 py-1 text-xs text-ink-muted"
              >
                <option value="">All data (unscoped)</option>
                {spaces.map((w) => (
                  <option key={w.id} value={w.slug}>{w.name}</option>
                ))}
              </select>
            )}
          <div className="telemetry text-ink-faint">
            {new Date().toISOString().slice(0, 10)} · OPS NORMAL
          </div>
          </div>
          <div className="flex items-center gap-5 text-sm">
            {fleet && (
              <span className="text-ink-muted">
                THREAT{" "}
                <span className={`font-semibold uppercase ${threatTone[fleet.threat_level]}`}>
                  {fleet.threat_level}
                </span>
              </span>
            )}
            {user && (
              <button onClick={() => navigate("/account")}
                className="text-ink-muted hover:text-ink" title="Account security">
                {user.full_name}
              </button>
            )}
            <button
              onClick={() => api.logout().then(() => navigate("/login"))}
              className="flex items-center gap-1.5 text-ink-muted hover:text-ink"
              title="Sign out">
              <LogOut size={15} />
            </button>
          </div>
        </header>

        {/* Mission ribbon — "can the mission still succeed?" from any screen */}
        {fleet && fleet.missions.length > 0 && (
          <div className="flex items-center gap-6 border-b border-line bg-navy px-6 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
              Mission assurance
            </span>
            {fleet.missions.map((m) => (
              <button key={m.mission_id} onClick={() => navigate("/missioniq")}
                className="flex min-w-[160px] items-center gap-2 text-left">
                <span className="truncate text-xs text-ink-muted">{m.name}</span>
                <span className="telemetry text-xs">{m.score}</span>
                <span className="w-16"><ScoreBar score={m.score} /></span>
              </button>
            ))}
          </div>
        )}

        <main id="main" className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
