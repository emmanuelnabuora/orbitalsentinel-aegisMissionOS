import { useCallback, useEffect, useState } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/lib/api";
import type { MFASetup, User } from "@/lib/types";
import { Card, PageHeader } from "@/components/ui";
import { personaForExactRole } from "@/lib/workspaces";

export default function Account() {
  const [user, setUser] = useState<User | null>(null);
  const [setup, setSetup] = useState<MFASetup | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.me().then(setUser).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  async function act(fn: () => Promise<void>) {
    setError(null);
    try { await fn(); } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed");
    }
  }

  if (!user) return <p className="text-sm text-ink-muted">Loading…</p>;

  return (
    <div>
      <PageHeader question="Is my account secure?" title="Account Security" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            <ShieldCheck size={14} /> Multi-factor authentication
          </h2>

          {user.mfa_enabled && !recovery && (
            <>
              <p className="text-sm text-mission">MFA is enabled on this account.</p>
              <p className="mt-2 text-sm text-ink-muted">
                Disabling requires a current authenticator or recovery code.
              </p>
              <div className="mt-3 flex gap-2">
                <input value={code} onChange={(e) => setCode(e.target.value)}
                  placeholder="Code" className="telemetry w-36 rounded border border-line bg-navy px-3 py-2 !text-sm" />
                <button
                  onClick={() => act(async () => {
                    await api.mfaDisable(code.trim());
                    setCode(""); load();
                  })}
                  className="rounded border border-critical/50 px-3 py-2 text-sm text-critical hover:bg-critical/10">
                  Disable MFA
                </button>
              </div>
            </>
          )}

          {!user.mfa_enabled && !setup && (
            <>
              <p className="text-sm text-ink-muted">
                Add a second factor. You will scan a QR code with any TOTP
                authenticator (1Password, Google Authenticator, ...).
              </p>
              <button
                onClick={() => act(async () => setSetup(await api.mfaSetup()))}
                className="mt-4 rounded bg-orbital text-on-accent px-4 py-2 text-sm font-semibold hover:bg-orbital-deep">
                Set up MFA
              </button>
            </>
          )}

          {setup && !recovery && (
            <div className="space-y-3">
              <p className="text-sm text-ink-muted">1. Scan with your authenticator:</p>
              <div className="w-44 rounded bg-white p-2"
                dangerouslySetInnerHTML={{ __html: setup.qr_svg }} />
              <p className="text-sm text-ink-muted">
                Or enter manually: <span className="telemetry !text-sm">{setup.secret}</span>
              </p>
              <p className="text-sm text-ink-muted">2. Enter the current code to activate:</p>
              <div className="flex gap-2">
                <input value={code} onChange={(e) => setCode(e.target.value)}
                  placeholder="000000" inputMode="numeric"
                  className="telemetry w-36 rounded border border-line bg-navy px-3 py-2 !text-sm tracking-[0.3em]" />
                <button
                  onClick={() => act(async () => {
                    const r = await api.mfaActivate(code.trim());
                    setRecovery(r.recovery_codes);
                    setSetup(null); setCode(""); load();
                  })}
                  className="rounded bg-mission/90 px-4 py-2 text-sm font-semibold hover:bg-mission">
                  Activate
                </button>
              </div>
            </div>
          )}

          {recovery && (
            <div>
              <p className="text-sm font-semibold text-amber">
                Recovery codes — shown once. Store them securely now.
              </p>
              <div className="telemetry mt-3 grid grid-cols-2 gap-x-8 gap-y-1.5 rounded border border-line bg-navy p-4 !text-sm">
                {recovery.map((c) => <span key={c}>{c}</span>)}
              </div>
              <button onClick={() => setRecovery(null)}
                className="mt-3 rounded border border-line px-3 py-1.5 text-xs hover:border-orbital">
                I have stored these codes
              </button>
            </div>
          )}
          {error && <p className="mt-3 text-sm text-critical">{error}</p>}
        </Card>

        <Card>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-ink-faint">
            <KeyRound size={14} /> Identity
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-faint">Name</dt><dd>{user.full_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-faint">Email</dt><dd className="text-ink-muted">{user.email}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-faint">Roles</dt>
              <dd className="flex flex-wrap justify-end gap-1.5">
                {user.roles.map((r) => {
                  const persona = personaForExactRole(r);
                  const cls = "rounded border px-1.5 py-0.5 text-[11px] uppercase transition-colors";
                  return persona ? (
                    <Link
                      key={r}
                      to={persona.route}
                      title={`Open ${persona.title}`}
                      className={`${cls} border-line text-ink-muted hover:border-orbital hover:text-orbital`}
                    >
                      {r}
                    </Link>
                  ) : (
                    <span key={r} className={`${cls} border-line text-ink-faint`}>{r}</span>
                  );
                })}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-ink-faint">
            Organization SSO (OIDC) is available when configured by your administrator;
            SSO sessions appear here identically.
          </p>
        </Card>
      </div>
    </div>
  );
}
