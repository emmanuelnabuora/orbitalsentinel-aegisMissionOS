import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { EmptyState, PageHeader, TableShell, Td, Th } from "@/components/ui";

const ALL_ROLES = [
  "admin", "operator", "analyst", "soc_manager",
  "incident_responder", "executive", "auditor", "viewer",
];
const CLEARANCES = ["unclassified", "cui", "secret"];

function RoleEditor({ user, onChanged }: { user: User; onChanged: (u: User) => void }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string[]>(user.roles);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onAway = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onAway);
    return () => document.removeEventListener("mousedown", onAway);
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.setUserRoles(user.id, pending);
      onChanged(updated);
      setOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to update roles");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => { setPending(user.roles); setOpen(!open); }}
        className="flex flex-wrap gap-1.5 rounded border border-transparent p-1 -m-1 hover:border-line"
      >
        {user.roles.map((r) => (
          <span key={r} className="rounded border border-line px-1.5 py-0.5 text-[11px] uppercase text-ink-muted">
            {r}
          </span>
        ))}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 w-56 rounded border border-line bg-midnight p-3 shadow-xl">
          <p className="mb-2 text-xs font-semibold text-ink-muted">Platform roles</p>
          <div className="mb-3 space-y-1.5">
            {ALL_ROLES.map((r) => (
              <label key={r} className="flex items-center gap-2 text-xs text-ink">
                <input
                  type="checkbox"
                  checked={pending.includes(r)}
                  onChange={(e) =>
                    setPending(e.target.checked ? [...pending, r] : pending.filter((x) => x !== r))
                  }
                />
                {r.replace("_", " ")}
              </label>
            ))}
          </div>
          {error && <p className="mb-2 text-xs text-critical">{error}</p>}
          <div className="flex justify-end gap-2">
            <button onClick={() => setOpen(false)} className="text-xs text-ink-muted hover:text-ink">
              Cancel
            </button>
            <button
              onClick={save}
              disabled={saving || pending.length === 0}
              className="rounded bg-orbital px-2.5 py-1 text-xs font-medium text-on-accent disabled:opacity-40"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ClearanceEditor({ user, onChanged }: { user: User; onChanged: (u: User) => void }) {
  const [saving, setSaving] = useState(false);

  async function change(clearance: string) {
    setSaving(true);
    try {
      onChanged(await api.setClearance(user.id, clearance));
    } catch {
      // no-op: value simply doesn't update if the request fails
    } finally {
      setSaving(false);
    }
  }

  const tone = user.clearance === "secret" ? "text-critical"
    : user.clearance === "cui" ? "text-amber" : "text-ink-muted";

  return (
    <select
      value={user.clearance ?? "unclassified"}
      onChange={(e) => change(e.target.value)}
      disabled={saving}
      aria-label={`Clearance for ${user.full_name}`}
      className={`rounded border border-line bg-navy px-2 py-1 text-xs uppercase ${tone}`}
    >
      {CLEARANCES.map((c) => <option key={c} value={c}>{c}</option>)}
    </select>
  );
}

export default function Admin() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    api.users("?limit=100").then((p) => setUsers(p.items)).catch((e) => {
      if (e instanceof ApiError && e.status === 403) setForbidden(true);
    });
  }, []);

  function patch(updated: User) {
    setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? prev);
  }

  return (
    <div>
      <PageHeader question="Who can do what?" title="Administration" />
      {forbidden && (
        <EmptyState title="Admin role required"
          body="User management is restricted to administrators. Your access attempt has been logged." />
      )}
      {users && (
        <TableShell>
          <thead>
            <tr><Th>Name</Th><Th>Email</Th><Th>Roles</Th><Th>Clearance</Th><Th>Status</Th></tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <Td className="font-medium">{u.full_name}</Td>
                <Td className="text-ink-muted">{u.email}</Td>
                <Td><RoleEditor user={u} onChanged={patch} /></Td>
                <Td><ClearanceEditor user={u} onChanged={patch} /></Td>
                <Td className={u.is_active ? "text-mission" : "text-critical"}>
                  {u.is_active ? "Active" : "Deactivated"}
                </Td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      )}
    </div>
  );
}
