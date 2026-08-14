/** Role-aware workspaces: persona definitions and routing rules.
 *
 * A user's home workspace is their highest-precedence role. Platform
 * admins (global "admin" role) land on the Platform workspace;
 * workspace-membership admins are Organization admins.
 */

export type Persona =
  | "platform"
  | "org"
  | "operator"
  | "analyst"
  | "soc"
  | "responder"
  | "executive"
  | "auditor";

export interface PersonaDef {
  id: Persona;
  title: string;
  eyebrow: string;
  route: string;
  /** nav paths visible for this persona, in order */
  nav: string[];
}

export const PERSONAS: Record<Persona, PersonaDef> = {
  platform: {
    id: "platform",
    title: "Platform Administration",
    eyebrow: "Platform Administrator",
    route: "/workspace/platform",
    nav: ["*"], // platform admins see everything
  },
  org: {
    id: "org",
    title: "Organization Administration",
    eyebrow: "Organization Administrator",
    route: "/workspace/org",
    nav: ["/workspace/org", "/", "/assets", "/alerts", "/investigations", "/missioniq", "/reports", "/account"],
  },
  operator: {
    id: "operator",
    title: "Mission Operations",
    eyebrow: "Mission Operator",
    route: "/workspace/operator",
    nav: ["/workspace/operator", "/ops", "/assets", "/missioniq", "/digital-twin", "/alerts", "/account"],
  },
  analyst: {
    id: "analyst",
    title: "Security Analysis",
    eyebrow: "Security Analyst",
    route: "/workspace/analyst",
    nav: ["/workspace/analyst", "/alerts", "/investigations", "/threat-intel", "/quantumshield", "/sentinel", "/account"],
  },
  soc: {
    id: "soc",
    title: "SOC Command",
    eyebrow: "SOC Manager",
    route: "/workspace/soc",
    nav: ["/workspace/soc", "/alerts", "/investigations", "/threat-intel", "/reports", "/account"],
  },
  responder: {
    id: "responder",
    title: "Incident Response",
    eyebrow: "Incident Responder",
    route: "/workspace/responder",
    nav: ["/workspace/responder", "/investigations", "/alerts", "/sentinel", "/account"],
  },
  executive: {
    id: "executive",
    title: "Executive Overview",
    eyebrow: "Executive",
    route: "/workspace/executive",
    nav: ["/workspace/executive", "/reports", "/account"],
  },
  auditor: {
    id: "auditor",
    title: "Audit & Compliance",
    eyebrow: "Auditor",
    route: "/workspace/auditor",
    nav: ["/workspace/auditor", "/reports", "/account"],
  },
};

/** Precedence when a user holds several roles. */
const ROLE_TO_PERSONA: [string, Persona][] = [
  ["admin", "platform"],
  ["soc_manager", "soc"],
  ["incident_responder", "responder"],
  ["operator", "operator"],
  ["analyst", "analyst"],
  ["executive", "executive"],
  ["auditor", "auditor"],
  ["viewer", "analyst"],
];

export function personaFor(roles: string[], isWorkspaceAdmin = false): PersonaDef {
  for (const [role, persona] of ROLE_TO_PERSONA) {
    if (roles.includes(role)) return PERSONAS[persona];
  }
  if (isWorkspaceAdmin) return PERSONAS.org;
  return PERSONAS.analyst;
}

/** Direct role -> persona lookup (no precedence). Used for role badges so a
 * user holding several roles can jump into any one of their workspaces,
 * not just the highest-precedence one personaFor() resolves to. */
export function personaForExactRole(role: string): PersonaDef | null {
  const match = ROLE_TO_PERSONA.find(([r]) => r === role);
  return match ? PERSONAS[match[1]] : null;
}

export function canSee(persona: PersonaDef, path: string): boolean {
  return persona.nav.includes("*") || persona.nav.includes(path);
}
