import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, PageHeader, Stat, TableShell, Td, Th, timeAgo } from "@/components/ui";
import type { Page as P, User, Workspace } from "@/lib/types";

// Auto-slug: lowercase, hyphenate, strip anything outside [a-z0-9-] — must
// stay in sync with the backend's _SLUG_RE (lowercase alphanumeric + hyphens).
function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function NewWorkspaceForm({ onCreated }: { onCreated: (ws: Workspace) => void }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const effectiveSlug = slugTouched ? slug : slugify(name);
  const slugValid = /^[a-z0-9](?:[a-z0-9-]{1,78})[a-z0-9]$/.test(effectiveSlug);

  const create = async () => {
    setErr(null);
    setSaving(true);
    try {
      const ws = await api.createWorkspace(name.trim(), effectiveSlug);
      onCreated(ws);
      setName("");
      setSlug("");
      setSlugTouched(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create workspace");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <h3 className="mb-3 text-sm font-semibold">New client workspace</h3>
      <div className="space-y-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Client / organization name"
          aria-label="Workspace name"
          className="w-full rounded border border-line bg-navy px-3 py-2 text-sm"
        />
        <div>
          <input
            value={effectiveSlug}
            onChange={(e) => { setSlug(e.target.value); setSlugTouched(true); }}
            placeholder="workspace-slug"
            aria-label="Workspace slug"
            className="w-full rounded border border-line bg-navy px-3 py-2 text-sm telemetry"
          />
          <p className="mt-1 text-xs text-ink-muted">
            Lowercase, hyphens only — auto-filled from the name, editable if you need something specific.
            This becomes the workspace's permanent identifier and can&apos;t be changed later.
          </p>
        </div>
        <button
          onClick={create}
          disabled={!name.trim() || !slugValid || saving}
          className="rounded bg-orbital text-on-accent px-4 py-2 text-sm font-medium disabled:opacity-40"
        >
          {saving ? "Creating…" : "Create workspace"}
        </button>
        {err && <p className="text-sm text-critical">{err}</p>}
        <p className="text-xs text-ink-muted">
          You&apos;re added as this workspace&apos;s admin automatically. Invite the client&apos;s
          own admin and hand off from the workspace&apos;s Organization Administration page.
        </p>
      </div>
    </Card>
  );
}

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
      <div className="grid grid-cols-2 gap-4">
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
        <NewWorkspaceForm onCreated={(ws) => setSpaces((prev) => [...prev, ws])} />
      </div>
    </div>
  );
}
