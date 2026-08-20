export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface User {
  id: string; email: string; full_name: string; roles: string[]; is_active: boolean; clearance?: string;
  mfa_enabled: boolean;
}
export interface LoginResult { mfaRequired: boolean; mfaToken?: string }
export interface MFASetup { secret: string; otpauth_uri: string; qr_svg: string }
export interface Asset {
  classification: string;
  id: string; name: string; description: string | null; asset_type: string;
  status: string; criticality: string; attributes: Record<string, unknown>;
  created_at: string; updated_at: string;
}
export interface Mission {
  id: string; name: string; description: string | null; status: string;
  priority: string; owner_id: string | null; created_at: string;
}
export interface Alert {
  classification: string;
  id: string; title: string; description: string | null; severity: string;
  status: string; source: string; asset_id: string | null; asset_name: string | null;
  assigned_to: string | null; incident_id: string | null; created_at: string;
}
export interface IncidentEvent { id: string; at: string; kind: string; message: string }
export interface Incident {
  id: string; title: string; summary: string | null; severity: string; status: string;
  created_at: string;
}
export interface IncidentDetail extends Incident { events: IncidentEvent[]; alerts: Alert[] }
export interface CryptoRecord {
  id: string; asset_id: string; asset_name: string | null; kind: string;
  algorithm: string; key_size: number | null; subject: string | null;
  expires_at: string | null; pqc_ready: boolean;
}
export interface QuantumReadiness {
  score: number; total_records: number; pqc_ready_records: number;
  vulnerable_records: number; vulnerable_by_algorithm: Record<string, number>;
  exposed_assets: string[]; recommendations: string[];
}
export interface MissionAssurance {
  mission_id: string; name: string; status: string; score: number; health: string;
  asset_count: number; degraded_assets: number; offline_assets: number;
  open_alerts: number; factors: string[];
}
export interface FleetSummary {
  average_score: number; threat_level: string; missions: MissionAssurance[];
  total_assets: number; open_alerts: number; open_incidents: number;
}
export interface GraphNode {
  id: string; kind: string; label: string; status: string | null; criticality: string | null;
}
export interface GraphEdge { source: string; target: string; kind: string; criticality: string }
export interface MissionGraph { nodes: GraphNode[]; edges: GraphEdge[] }
export interface ChatResponse { answer: string; provider: string; suggested_actions: string[] }
export interface IncidentAnalysis {
  summary: string; root_cause_hypotheses: string[]; recommended_actions: string[];
  provider: string;
}

export interface ThreatIndicator {
  id: string; indicator_type: string; value: string; category: string;
  severity: string; confidence: number; source: string; description: string | null;
  active: boolean; first_seen: string; last_seen: string;
}
export interface ThreatMatch {
  id: string; indicator_id: string; asset_id: string; alert_id: string | null;
  matched_on: string; created_at: string; indicator_value: string | null;
  indicator_category: string | null; severity: string | null; asset_name: string | null;
}
export interface IngestResult { source: string; received: number; created: number; updated: number }
export interface CorrelationResult {
  indicators_checked: number; assets_checked: number; new_matches: number;
  alerts_raised: number; matches: ThreatMatch[];
}
export interface ThreatIntelSummary {
  active_indicators: number; by_severity: Record<string, number>;
  by_category: Record<string, number>; total_matches: number;
  sources: Record<string, number>; last_ingest: string | null;
}
export interface ReportSection {
  heading: string; body: string; columns: string[] | null; rows: string[][] | null;
}
export interface ReportContent { summary: string; sections: ReportSection[] }
export interface Report {
  id: string; kind: string; title: string; subject_id: string | null;
  provider: string; generated_by: string | null; created_at: string;
}
export interface ReportDetail extends Report { content: ReportContent }
export interface Perturbation {
  kind: "set_status" | "offline" | "add_alerts" | "remove_asset";
  asset_id: string; status?: string; magnitude?: number;
}
export interface MissionProjection {
  mission_id: string; name: string; baseline_score: number; projected_score: number;
  delta: number; baseline_health: string; projected_health: string;
  crossed_threshold: boolean; projected_factors: string[];
}
export interface ImpactedAsset {
  asset_id: string; name: string; baseline_status: string; projected_status: string;
  removed: boolean; added_alerts: number;
}
export interface SimulationResult {
  scenario_name: string; baseline_average: number; projected_average: number;
  average_delta: number; missions_at_risk_before: number; missions_at_risk_after: number;
  newly_at_risk: string[]; impacted_assets: ImpactedAsset[];
  missions: MissionProjection[]; summary: string;
}

export interface Scenario {
  id: string; name: string; description: string | null;
  perturbations: { kind: string; asset_id: string; status?: string; magnitude?: number }[];
  created_by: string | null; last_run_at: string | null; created_at: string;
}
export interface Workspace { id: string; name: string; slug: string; created_at: string }
export interface Member { user_id: string; role: string; custom_role_id: string | null }
export interface InviteCreated {
  id: string; email: string; role: string; expires_at: string; used_at: string | null; token: string;
}
export interface ApiKeyCreated {
  id: string; name: string; prefix: string; key: string; created_at: string;
  last_used_at: string | null; revoked_at: string | null;
}
export interface ApiKeyInfo {
  id: string; name: string; prefix: string; created_at: string;
  last_used_at: string | null; revoked_at: string | null;
}
export interface ServiceAccount {
  id: string; email: string; full_name: string; created_at: string; keys: ApiKeyInfo[];
}
export interface AuditEntry {
  id: string; actor_id: string | null; action: string; resource_type: string | null;
  resource_id: string | null; detail: Record<string, unknown> | null; created_at: string;
}

export interface PermissionCatalog {
  permissions: string[]; groups: Record<string, string[]>; sensitive: string[];
}
export interface CustomRole {
  id: string; name: string; slug: string; description: string | null;
  status: "active" | "pending" | "rejected"; permission_values: string[]; created_at: string;
}
export interface Approval {
  id: string; kind: string; subject_id: string; payload: Record<string, unknown>;
  status: string; requested_by: string; decided_by: string | null;
  decided_at: string | null; reason: string | null; created_at: string;
}

export interface Notif {
  id: string; workspace_id: string | null; kind: string; title: string;
  body: string; link: string | null; read_at: string | null; created_at: string;
}
export interface NotifInbox { unread: number; items: Notif[] }
