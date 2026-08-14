import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { api } from "@/lib/api";
import type { NotifInbox } from "@/lib/types";
import { timeAgo } from "./ui";

export default function NotificationBell() {
  const [inbox, setInbox] = useState<NotifInbox | null>(null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const load = () => api.notifications().then(setInbox).catch(() => undefined);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    const onClickAway = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickAway);
    return () => { clearInterval(t); document.removeEventListener("mousedown", onClickAway); };
  }, []);

  const unread = inbox?.unread ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        className="relative rounded p-2 text-ink-muted hover:bg-raised hover:text-ink"
      >
        <Bell size={16} strokeWidth={1.75} />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-critical px-1 text-[10px] font-bold text-on-accent">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-96 rounded border border-line bg-midnight shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <p className="text-sm font-semibold">Notifications</p>
            {unread > 0 && (
              <button
                onClick={async () => { await api.markAllNotifsRead().catch(() => undefined); load(); }}
                className="text-xs text-orbital hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {(inbox?.items ?? []).length === 0 && (
              <p className="p-4 text-sm text-ink-faint">Nothing yet. Alerts, approvals, and team activity land here.</p>
            )}
            {(inbox?.items ?? []).map((n) => (
              <Link
                key={n.id}
                to={n.link ?? "#"}
                onClick={async () => {
                  if (!n.read_at) await api.markNotifRead(n.id).catch(() => undefined);
                  setOpen(false); load();
                }}
                className={`block border-b border-line px-4 py-3 hover:bg-raised ${n.read_at ? "opacity-60" : ""}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm">{n.title}</p>
                  {!n.read_at && <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-orbital text-on-accent" />}
                </div>
                {n.body && <p className="mt-0.5 text-xs text-ink-muted">{n.body}</p>}
                <p className="telemetry mt-1 text-[10px] text-ink-faint">{timeAgo(n.created_at)}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
