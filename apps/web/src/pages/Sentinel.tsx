import { type FormEvent, useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Card, PageHeader } from "@/components/ui";

interface Turn { role: "user" | "ai"; text: string; actions?: string[]; provider?: string }

const STARTERS = [
  "What is our mission assurance?",
  "What needs attention right now?",
  "Are we quantum ready?",
];

export default function Sentinel() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ provider: string; live: boolean; model: string | null } | null>(null);

  useEffect(() => {
    api.sentinelStatus().then(setStatus).catch(() => undefined);
  }, []);
  const endRef = useRef<HTMLDivElement>(null);

  async function send(message: string) {
    if (!message.trim() || busy) return;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput(""); setBusy(true);
    try {
      const r = await api.sentinelChat(message);
      setTurns((t) => [...t, { role: "ai", text: r.answer, actions: r.suggested_actions,
                               provider: r.provider }]);
    } catch {
      setTurns((t) => [...t, { role: "ai", text: "SentinelAI is unreachable." }]);
    } finally {
      setBusy(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  function submit(e: FormEvent) { e.preventDefault(); void send(input); }

  return (
    <div className="flex h-[calc(100vh-160px)] flex-col">
      <PageHeader question="What should I do next?" title="SentinelAI Copilot">
        {status && (
          <span
            className={`telemetry flex items-center gap-1.5 rounded border px-2 py-1 text-[10px] uppercase tracking-wider ${
              status.live ? "border-mission/50 text-mission" : "border-line text-ink-faint"}`}
            title={status.provider}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${status.live ? "bg-mission" : "bg-ink-faint"}`} />
            {status.live ? `Live · ${status.model}` : "Rules engine"}
          </span>
        )}
      </PageHeader>
      <Card className="flex flex-1 flex-col overflow-hidden !p-0">
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {turns.length === 0 && (
            <div className="mx-auto max-w-md pt-10 text-center">
              <Sparkles className="mx-auto text-quantum" size={22} />
              <p className="mt-3 text-sm text-ink-muted">
                Ask about missions, alerts, incidents, or quantum readiness.
                Every answer is grounded in live platform data.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {STARTERS.map((s) => (
                  <button key={s} onClick={() => void send(s)}
                    className="rounded-full border border-line px-3 py-1.5 text-xs text-ink-muted hover:border-quantum hover:text-ink">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i} className={t.role === "user" ? "flex justify-end" : "flex"}>
              <div className={`max-w-[75%] rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
                t.role === "user" ? "bg-orbital/20" : "border border-line bg-navy"}`}>
                <p>{t.text}</p>
                {t.actions && t.actions.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-ink-muted">
                    {t.actions.map((a, j) => <li key={j}>{a}</li>)}
                  </ul>
                )}
                {t.provider && (
                  <p className="telemetry mt-2 !text-[10px] text-ink-faint">via {t.provider}</p>
                )}
              </div>
            </div>
          ))}
          {busy && <p className="text-xs text-ink-faint">SentinelAI is reasoning…</p>}
          <div ref={endRef} />
        </div>
        <form onSubmit={submit} className="flex gap-2 border-t border-line p-3">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Ask SentinelAI…"
            className="flex-1 rounded border border-line bg-navy px-3 py-2 text-sm" />
          <button disabled={busy}
            className="rounded bg-quantum px-4 text-sm font-semibold hover:opacity-90 disabled:opacity-60">
            Send
          </button>
        </form>
      </Card>
    </div>
  );
}
