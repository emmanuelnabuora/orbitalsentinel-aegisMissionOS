/** Typed API client with bearer auth and silent refresh-token rotation. */

import type {
  Approval, AuditEntry, NotifInbox, ApiKeyCreated, CustomRole, InviteCreated, Member, PermissionCatalog, ServiceAccount, Workspace,
  Alert, CorrelationResult, IngestResult, LoginResult, MFASetup,
  Perturbation, Report, ReportDetail, Scenario, SimulationResult,
  ThreatIndicator, ThreatIntelSummary, ThreatMatch, Asset, ChatResponse, CryptoRecord, FleetSummary, Incident, IncidentAnalysis,
  IncidentDetail, Mission, MissionAssurance, MissionGraph, Page, QuantumReadiness, User,
} from "./types";

const BASE = "/api/v1";
const STORE = "aegis.tokens"; // sessionStorage: cleared when the tab closes

interface Tokens { access: string; refresh: string }

function loadTokens(): Tokens | null {
  const raw = sessionStorage.getItem(STORE);
  return raw ? (JSON.parse(raw) as Tokens) : null;
}
function saveTokens(t: Tokens | null) {
  if (t) sessionStorage.setItem(STORE, JSON.stringify(t));
  else sessionStorage.removeItem(STORE);
}

export function isAuthenticated(): boolean {
  return loadTokens() !== null;
}

let onSessionExpired: () => void = () => {};
export function setSessionExpiredHandler(fn: () => void) { onSessionExpired = fn; }

async function refreshTokens(): Promise<boolean> {
  const t = loadTokens();
  if (!t) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: t.refresh }),
  });
  if (!res.ok) { saveTokens(null); return false; }
  const body = await res.json();
  saveTokens({ access: body.access_token, refresh: body.refresh_token });
  return true;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

import { activeWorkspace } from "./workspaceContext";

async function request<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const t = loadTokens();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ws = activeWorkspace();
  if (ws) headers["X-Workspace"] = ws;
  if (t) headers.Authorization = `Bearer ${t.access}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && !retried && t) {
    if (await refreshTokens()) return request<T>(path, init, true);
    onSessionExpired();
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, detail.detail ?? `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  async login(email: string, password: string): Promise<LoginResult> {
    const body = await request<{
      mfa_required: boolean; mfa_token: string | null;
      access_token: string | null; refresh_token: string | null;
    }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    if (body.mfa_required && body.mfa_token) {
      return { mfaRequired: true, mfaToken: body.mfa_token };
    }
    if (body.access_token && body.refresh_token) {
      saveTokens({ access: body.access_token, refresh: body.refresh_token });
    }
    return { mfaRequired: false };
  },
  async mfaVerify(mfaToken: string, code: string): Promise<void> {
    const body = await request<{ access_token: string; refresh_token: string }>(
      "/auth/mfa/verify",
      { method: "POST", body: JSON.stringify({ mfa_token: mfaToken, code }) },
    );
    saveTokens({ access: body.access_token, refresh: body.refresh_token });
  },
  mfaSetup: () => request<MFASetup>("/auth/mfa/setup", { method: "POST" }),
  mfaActivate: (code: string) =>
    request<{ recovery_codes: string[] }>("/auth/mfa/activate", {
      method: "POST", body: JSON.stringify({ code }),
    }),
  mfaDisable: (code: string) =>
    request("/auth/mfa/disable", { method: "POST", body: JSON.stringify({ code }) }),
  ssoStatus: () => request<{ configured: boolean }>("/auth/sso/status"),
  ssoBegin: () => request<{ authorization_url: string }>("/auth/sso/begin"),
  async ssoCallback(code: string, state: string): Promise<void> {
    const body = await request<{ access_token: string; refresh_token: string }>(
      "/auth/sso/callback",
      { method: "POST", body: JSON.stringify({ code, state }) },
    );
    saveTokens({ access: body.access_token, refresh: body.refresh_token });
  },
  async logout(): Promise<void> {
    const t = loadTokens();
    if (t) {
      await request("/auth/logout", {
        method: "POST", body: JSON.stringify({ refresh_token: t.refresh }),
      }).catch(() => undefined);
    }
    saveTokens(null);
  },
  me: () => request<User>("/auth/me"),
  workspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (name: string, slug: string) =>
    request<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name, slug }) }),
  workspaceMembers: (slug: string) => request<Member[]>(`/workspaces/${slug}/members`),
  addMember: (slug: string, user_id: string, role: string) =>
    request<Member>(`/workspaces/${slug}/members`, { method: "POST", body: JSON.stringify({ user_id, role }) }),
  setMemberRole: (slug: string, userId: string, role: string) =>
    request<Member>(`/workspaces/${slug}/members/${userId}`, { method: "PUT", body: JSON.stringify({ role }) }),
  removeMember: (slug: string, userId: string) =>
    request<void>(`/workspaces/${slug}/members/${userId}`, { method: "DELETE" }),
  createInvite: (slug: string, email: string, role: string) =>
    request<InviteCreated>(`/workspaces/${slug}/invites`, { method: "POST", body: JSON.stringify({ email, role }) }),
  redeemInvite: (token: string, password: string, full_name: string) =>
    request<User>("/invites/redeem", { method: "POST", body: JSON.stringify({ token, password, full_name }) }),
  createServiceAccount: (slug: string, name: string, email: string, role = "operator") =>
    request<User>(`/workspaces/${slug}/service-accounts`, { method: "POST", body: JSON.stringify({ name, email, role }) }),
  listServiceAccounts: (slug: string) =>
    request<ServiceAccount[]>(`/workspaces/${slug}/service-accounts`),
  mintApiKey: (slug: string, accountId: string, name: string) =>
    request<ApiKeyCreated>(`/workspaces/${slug}/service-accounts/${accountId}/keys`, { method: "POST", body: JSON.stringify({ name }) }),
  revokeApiKey: (slug: string, keyId: string) =>
    request<void>(`/workspaces/${slug}/service-accounts/keys/${keyId}`, { method: "DELETE" }),
  auditLog: (limit = 100) => request<AuditEntry[]>(`/audit?limit=${limit}`),
  notifications: () => request<NotifInbox>("/notifications"),
  markNotifRead: (id: string) => request<void>(`/notifications/${id}/read`, { method: "POST" }),
  markAllNotifsRead: () => request<void>("/notifications/read-all", { method: "POST" }),
  getPreferences: () => request<{ data: Record<string, unknown> }>("/preferences"),
  putPreferences: (data: Record<string, unknown>) =>
    request<{ data: Record<string, unknown> }>("/preferences", { method: "PUT", body: JSON.stringify({ data }) }),
  permissionCatalog: () => request<PermissionCatalog>("/workspaces/rbac/catalog"),
  customRoles: (slug: string) => request<CustomRole[]>(`/workspaces/${slug}/roles`),
  createCustomRole: (slug: string, body: { name: string; slug: string; description?: string; groups: string[] }) =>
    request<CustomRole>(`/workspaces/${slug}/roles`, { method: "POST", body: JSON.stringify(body) }),
  assignCustomRole: (slug: string, userId: string, role_slug: string) =>
    request<void>(`/workspaces/${slug}/members/${userId}/custom-role`, { method: "PUT", body: JSON.stringify({ role_slug }) }),
  approvals: (slug: string) => request<Approval[]>(`/workspaces/${slug}/approvals`),
  decideApproval: (slug: string, id: string, approve: boolean, reason?: string) =>
    request<Approval>(`/workspaces/${slug}/approvals/${id}`, { method: "POST", body: JSON.stringify({ approve, reason }) }),
  users: (q = "") => request<Page<User>>(`/users${q}`),
  setUserRoles: (userId: string, roles: string[]) =>
    request<User>(`/users/${userId}/roles`, { method: "PUT", body: JSON.stringify({ roles }) }),
  setClearance: (userId: string, clearance: string) =>
    request<User>(`/users/${userId}/clearance`, { method: "PUT", body: JSON.stringify({ clearance }) }),
  unassignCustomRole: (slug: string, userId: string) =>
    request<void>(`/workspaces/${slug}/members/${userId}/custom-role`, { method: "DELETE" }),
  assets: (q = "") => request<Page<Asset>>(`/assets${q}`),
  asset: (id: string) => request<Asset>(`/assets/${id}`),
  missions: (q = "") => request<Page<Mission>>(`/missions${q}`),
  missionGraph: (id: string) => request<MissionGraph>(`/missions/${id}/graph`),
  alerts: (q = "") => request<Page<Alert>>(`/alerts${q}`),
  updateAlert: (id: string, body: object) =>
    request<Alert>(`/alerts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  incidents: (q = "") => request<Page<Incident>>(`/incidents${q}`),
  incident: (id: string) => request<IncidentDetail>(`/incidents/${id}`),
  updateIncident: (id: string, body: object) =>
    request<Incident>(`/incidents/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  addIncidentNote: (id: string, message: string) =>
    request(`/incidents/${id}/notes`, { method: "POST", body: JSON.stringify({ message }) }),
  quantumInventory: (q = "") => request<Page<CryptoRecord>>(`/quantum/inventory${q}`),
  quantumReadiness: () => request<QuantumReadiness>("/quantum/readiness"),
  fleet: () => request<FleetSummary>("/missioniq/summary"),
  assurance: (missionId: string) =>
    request<MissionAssurance>(`/missioniq/missions/${missionId}`),
  sentinelStatus: () => request<{ provider: string; live: boolean; model: string | null }>("/sentinel/status"),
  sentinelChat: (message: string) =>
    request<ChatResponse>("/sentinel/chat", { method: "POST", body: JSON.stringify({ message }) }),
  analyzeIncident: (id: string) =>
    request<IncidentAnalysis>(`/sentinel/incidents/${id}/analyze`, { method: "POST" }),
  threatSummary: () => request<ThreatIntelSummary>("/threat-intel/summary"),
  threatIndicators: (q = "") => request<Page<ThreatIndicator>>(`/threat-intel/indicators${q}`),
  threatIngest: () => request<IngestResult[]>("/threat-intel/ingest", { method: "POST" }),
  threatCorrelate: () =>
    request<CorrelationResult>("/threat-intel/correlate", { method: "POST" }),
  threatMatches: () => request<ThreatMatch[]>("/threat-intel/matches"),
  reports: (q = "") => request<Page<Report>>(`/reports${q}`),
  report: (id: string) => request<ReportDetail>(`/reports/${id}`),
  generateReport: (kind: string, subjectId?: string, title?: string) =>
    request<ReportDetail>("/reports", {
      method: "POST",
      body: JSON.stringify({ kind, subject_id: subjectId ?? null, title: title ?? null }),
    }),
  simulate: (name: string, perturbations: Perturbation[]) =>
    request<SimulationResult>("/digital-twin/simulate", {
      method: "POST", body: JSON.stringify({ name, perturbations }),
    }),
  listScenarios: () => request<Scenario[]>("/digital-twin/scenarios"),
  createScenario: (name: string, description: string | null, perturbations: Perturbation[]) =>
    request<Scenario>("/digital-twin/scenarios", {
      method: "POST", body: JSON.stringify({ name, description, perturbations }),
    }),
  runScenario: (id: string) =>
    request<SimulationResult>(`/digital-twin/scenarios/${id}/run`, { method: "POST" }),
  deleteScenario: (id: string) =>
    request(`/digital-twin/scenarios/${id}`, { method: "DELETE" }),
  reportPdfUrl: (id: string) => `/api/v1/reports/${id}/export.pdf`,
  async downloadReportPdf(id: string, filename: string): Promise<void> {
    const t = loadTokens();
    const res = await fetch(`/api/v1/reports/${id}/export.pdf`, {
      headers: t ? { Authorization: `Bearer ${t.access}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  },
};
