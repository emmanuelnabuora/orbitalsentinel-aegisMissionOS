import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-line bg-midnight p-5 ${className}`}>{children}</div>
  );
}

const STATUS_COLOR: Record<string, string> = {
  operational: "bg-mission", degraded: "bg-amber", offline: "bg-critical",
  unknown: "bg-ink-faint", active: "bg-mission", planning: "bg-orbital",
  suspended: "bg-amber", completed: "bg-ink-faint",
  open: "bg-critical", acknowledged: "bg-amber", investigating: "bg-orbital",
  contained: "bg-quantum", resolved: "bg-mission",
};
export function StatusDot({ value }: { value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${STATUS_COLOR[value] ?? "bg-ink-faint"}`} />
      <span className="capitalize">{value}</span>
    </span>
  );
}

const SEV_STYLE: Record<string, string> = {
  critical: "bg-critical/15 text-critical border-critical/40",
  high: "bg-amber/15 text-amber border-amber/40",
  medium: "bg-orbital/15 text-[#7EA6F7] border-orbital/40",
  low: "bg-ink-faint/15 text-ink-muted border-line",
  info: "bg-ink-faint/15 text-ink-muted border-line",
};
export function ClassificationBadge({ value }: { value: string }) {
  if (!value || value === "unclassified") return null;
  const tone = value === "secret" ? "border-critical/50 text-critical" : "border-amber/50 text-amber";
  return (
    <span className={`telemetry rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${tone}`}>
      {value}
    </span>
  );
}

export function SeverityBadge({ value }: { value: string }) {
  return (
    <span className={`rounded border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${SEV_STYLE[value] ?? SEV_STYLE.low}`}>
      {value}
    </span>
  );
}

/** Every page answers one question — the question is the eyebrow. */
export function PageHeader({ question, title, children }: {
  question: string; title: string; children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-ink-faint">
          {question}
        </p>
        <h1 className="mt-1 text-xl font-bold">{title}</h1>
      </div>
      {children}
    </div>
  );
}

export function Stat({ label, value, tone = "text-ink", sub }: {
  label: string; value: string | number; tone?: string; sub?: string;
}) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-wider text-ink-faint">{label}</p>
      <p className={`telemetry mt-2 !text-3xl font-medium ${tone}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-ink-muted">{sub}</p>}
    </Card>
  );
}

export function ScoreBar({ score }: { score: number }) {
  const tone = score >= 80 ? "bg-mission" : score >= 50 ? "bg-amber" : "bg-critical";
  return (
    <div className="h-1.5 w-full rounded bg-navy">
      <div className={`h-1.5 rounded ${tone}`} style={{ width: `${score}%` }} />
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <Card className="py-12 text-center">
      <p className="font-semibold">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{body}</p>
    </Card>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
      {children}
    </th>
  );
}
export function Td({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <td className={`px-4 py-3 text-sm ${className}`}>{children}</td>;
}
export function TableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <table className="w-full border-collapse bg-midnight [&_tbody_tr]:border-t [&_tbody_tr]:border-line [&_tbody_tr:hover]:bg-raised">
        {children}
      </table>
    </div>
  );
}

export function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
