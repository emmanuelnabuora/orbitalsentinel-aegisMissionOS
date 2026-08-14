import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, PageHeader, TableShell, Td, Th } from "@/components/ui";
import { activeWorkspace } from "@/lib/workspaceContext";
import type { Approval, CustomRole, Member, PermissionCatalog } from "@/lib/types";

const WORKSPACE_ROLES = [
  "admin", "operator", "analyst", "soc_manager",
  "incident_responder", "executive", "auditor", "viewer",
];

function MemberRoleSelect({
  slug, member, onChanged,
}: { slug: string; member: Member; onChanged: () => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function change(role: string) {
    setSaving(true);
    setError(null);
    try {
      await api.setMemberRole(slug, member.user_id, role);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to change role");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <select
        value={member.role}
        onChange={(e) => change(e.target.value)}
        disabled={saving}
        aria-label="Workspace role"
        className="rounded border border-line bg-navy px-2 py-1 text-xs"
      >
        {WORKSPACE_ROLES.map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}
      </select>
      {error && <p className="mt-1 text-[11px] text-critical">{error}</p>}
    </div>
  );
}

function MemberCustomRoleSelect({
  slug, member, activeRoles, onChanged,
}: { slug: string; member: Member; activeRoles: CustomRole[]; onChanged: () => void }) {
  const [saving, setSaving] = useState(false);
  const current = activeRoles.find((r) => r.id === member.custom_role_id);

  async function change(roleId: string) {
    setSaving(true);
    try {
      if (roleId === "") {
        await api.unassignCustomRole(slug, member.user_id);
      } else {
        const role = activeRoles.find((r) => r.id === roleId);
        if (role) await api.assignCustomRole(slug, member.user_id, role.slug);
      }
      onChanged();
    } catch {
      // no-op: selection reverts on next render if it didn't take
    } finally {
      setSaving(false);
    }
  }

  return (
    <select
      value={current?.id ?? ""}
      onChange={(e) => change(e.target.value)}
      disabled={saving || activeRoles.length === 0}
      aria-label="Custom role"
      className="rounded border border-line bg-navy px-2 py-1 text-xs text-ink-muted disabled:opacity-40"
    >
      <option value="">— built-in only —</option>
      {activeRoles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select>
  );
}

export default function OrgAdmin() {
  const slug = activeWorkspace();
  const [members, setMembers] = useState<Member[]>([]);
  const [catalog, setCatalog] = useState<PermissionCatalog | null>(null);
  const [roles, setRoles] = useState<CustomRole[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [roleName, setRoleName] = useState("");
  const [roleGroups, setRoleGroups] = useState<string[]>([]);
  const [roleMsg, setRoleMsg] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [issued, setIssued] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = (s: string) => {
    api.workspaceMembers(s).then(setMembers).catch(() => undefined);
    api.customRoles(s).then(setRoles).catch(() => undefined);
    api.approvals(s).then(setApprovals).catch(() => undefined);
  };

  useEffect(() => {
    api.permissionCatalog().then(setCatalog).catch(() => undefined);
    if (slug) reload(slug);
  }, [slug]);

  if (!slug) {
    return (
      <PageHeader question="Which organization are you administering?" title="Organization Administration">
        <p className="text-sm text-ink-muted">Select a workspace from the header to manage its members.</p>
      </PageHeader>
    );
  }

  const invite = async () => {
    setErr(null);
    try {
      const r = await api.createInvite(slug, inviteEmail, inviteRole);
      setIssued(r.token);
      setInviteEmail("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Invite failed");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader question={`Who belongs to ${slug}, and with what role?`} title="Organization Administration" />
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Members</h3>
          <TableShell>
            <thead><tr><Th>User</Th><Th>Workspace role</Th><Th>Custom role</Th></tr></thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.user_id} className="border-t border-line">
                  <Td><span className="telemetry">{m.user_id.slice(0, 8)}</span></Td>
                  <Td><MemberRoleSelect slug={slug} member={m} onChanged={() => reload(slug)} /></Td>
                  <Td>
                    <MemberCustomRoleSelect
                      slug={slug} member={m}
                      activeRoles={roles.filter((r) => r.status === "active")}
                      onChanged={() => reload(slug)}
                    />
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-semibold">Invite a member</h3>
          <div className="space-y-3">
            <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="name@company.com" type="email" aria-label="Invitee email"
              className="w-full rounded border border-line bg-navy px-3 py-2 text-sm" />
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} aria-label="Invitee role"
              className="w-full rounded border border-line bg-navy px-3 py-2 text-sm">
              {WORKSPACE_ROLES.map((r) => (
                <option key={r} value={r}>{r.replace("_", " ")}</option>
              ))}
            </select>
            <button onClick={invite} disabled={!inviteEmail}
              className="rounded bg-orbital text-on-accent px-4 py-2 text-sm font-medium disabled:opacity-40">
              Create invite
            </button>
            {err && <p className="text-sm text-critical">{err}</p>}
            {issued && (
              <div className="rounded border border-amber/40 bg-amber/10 p-3">
                <p className="mb-1 text-xs uppercase tracking-wide text-amber">Invite token — shown once</p>
                <p className="telemetry break-all select-all">{issued}</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h3 className="mb-1 text-sm font-semibold">Custom roles</h3>
          <p className="mb-3 text-xs text-ink-muted">
            Compose a role from permission groups. Roles containing sensitive
            permissions activate only after a second admin approves.
          </p>
          <div className="mb-3 space-y-2">
            <input value={roleName} onChange={(e) => setRoleName(e.target.value)}
              placeholder="Role name (e.g. Compliance Reviewer)" aria-label="Custom role name"
              className="w-full rounded border border-line bg-navy px-3 py-2 text-sm" />
            <div className="flex flex-wrap gap-1.5">
              {Object.keys(catalog?.groups ?? {}).map((g) => {
                const on = roleGroups.includes(g);
                const sensitive = (catalog?.groups[g] ?? []).some((perm) => catalog?.sensitive.includes(perm));
                return (
                  <button key={g} type="button"
                    onClick={() => setRoleGroups(on ? roleGroups.filter((x) => x !== g) : [...roleGroups, g])}
                    className={`rounded border px-2 py-1 text-xs transition-colors ${
                      on ? "border-orbital bg-orbital/20 text-ink" : "border-line text-ink-muted hover:text-ink"}`}>
                    {g}{sensitive && <span className="ml-1 text-amber" title="Requires approval">●</span>}
                  </button>
                );
              })}
            </div>
            <button
              onClick={async () => {
                if (!slug) return;
                setRoleMsg(null);
                try {
                  const created = await api.createCustomRole(slug, {
                    name: roleName,
                    slug: roleName.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""),
                    groups: roleGroups,
                  });
                  setRoleMsg(created.status === "pending"
                    ? "Role created — awaiting a second admin's approval."
                    : "Role created and active.");
                  setRoleName(""); setRoleGroups([]); reload(slug);
                } catch (e) {
                  setRoleMsg(e instanceof Error ? e.message : "Role creation failed");
                }
              }}
              disabled={!roleName || roleGroups.length === 0}
              className="rounded bg-orbital text-on-accent px-4 py-2 text-sm font-medium disabled:opacity-40">
              Create role
            </button>
            {roleMsg && <p className="text-sm text-ink-muted">{roleMsg}</p>}
          </div>
          <TableShell>
            <thead><tr><Th>Role</Th><Th>Status</Th><Th>Permissions</Th></tr></thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.id} className="border-t border-line">
                  <Td>{r.name}</Td>
                  <Td>
                    <span className={r.status === "active" ? "text-mission" : r.status === "pending" ? "text-amber" : "text-critical"}>
                      {r.status}
                    </span>
                  </Td>
                  <Td className="telemetry text-xs text-ink-muted">{r.permission_values.length}</Td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Card>

        <Card>
          <h3 className="mb-1 text-sm font-semibold">Pending approvals</h3>
          <p className="mb-3 text-xs text-ink-muted">
            Sensitive grants need a second admin. You can't approve your own requests.
          </p>
          {approvals.length === 0 && <p className="text-sm text-ink-faint">Nothing waiting.</p>}
          <div className="space-y-3">
            {approvals.map((a) => (
              <div key={a.id} className="rounded border border-line p-3">
                <p className="text-sm">{String(a.payload["role_slug"] ?? a.kind)}</p>
                <p className="telemetry mb-2 text-xs text-amber">
                  {(a.payload["sensitive_permissions"] as string[] | undefined)?.join(", ")}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={async () => { if (slug) { await api.decideApproval(slug, a.id, true).catch(() => undefined); reload(slug); } }}
                    className="rounded bg-mission/20 px-3 py-1 text-xs text-mission">Approve</button>
                  <button
                    onClick={async () => { if (slug) { await api.decideApproval(slug, a.id, false).catch(() => undefined); reload(slug); } }}
                    className="rounded bg-critical/20 px-3 py-1 text-xs text-critical">Reject</button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
