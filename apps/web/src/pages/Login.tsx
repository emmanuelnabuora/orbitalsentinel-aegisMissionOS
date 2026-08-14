import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [ssoAvailable, setSsoAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.ssoStatus().then((s) => setSsoAvailable(s.configured)).catch(() => undefined);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      if (mfaToken) {
        await api.mfaVerify(mfaToken, code.trim());
        navigate("/");
        return;
      }
      const result = await api.login(email, password);
      if (result.mfaRequired && result.mfaToken) {
        setMfaToken(result.mfaToken);
      } else {
        navigate("/");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to reach AEGIS");
      if (mfaToken) setCode("");
    } finally {
      setBusy(false);
    }
  }

  async function sso() {
    setError(null);
    try {
      const { authorization_url } = await api.ssoBegin();
      window.location.assign(authorization_url);
    } catch {
      setError("SSO provider is unreachable");
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="brand-panel relative hidden overflow-hidden border-r border-line bg-midnight lg:block">
        <div className="absolute inset-0 opacity-40"
          style={{ backgroundImage:
            "radial-gradient(circle at 30% 20%, rgba(37,99,235,.25), transparent 45%)," +
            "radial-gradient(circle at 75% 70%, rgba(124,58,237,.18), transparent 40%)" }} />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <img src="/brand/shield.png" alt="OrbitalSentinel" className="h-10 w-10 rounded object-cover" />
            <div>
              <p className="font-bold tracking-wide">AEGIS MissionOS</p>
              <p className="text-[10px] uppercase tracking-[0.25em] text-ink-faint">OrbitalSentinel</p>
            </div>
          </div>
          <img src="/brand/orbitalsentinel-lockup.png" alt="OrbitalSentinel — Securing the orbital economy"
            className="mx-auto w-full max-w-sm select-none" draggable={false} />
          <div>
            <h1 className="max-w-md text-3xl font-bold leading-tight">
              The operating system for mission assurance.
            </h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-ink-muted">
              Observe, detect, investigate, understand, and respond — across Earth and space.
              Zero-trust by design; every action attributable.
            </p>
          </div>
          <p className="telemetry text-ink-faint">AUTHORIZED PERSONNEL · ALL SESSIONS AUDITED</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm">
          {!mfaToken ? (
            <>
              <h2 className="text-xl font-bold">Sign in</h2>
              <label className="mt-6 block text-xs font-medium uppercase tracking-wider text-ink-faint">
                Email
              </label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-1.5 w-full rounded border border-line bg-midnight px-3 py-2 text-sm" />
              <label className="mt-4 block text-xs font-medium uppercase tracking-wider text-ink-faint">
                Password
              </label>
              <input type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 w-full rounded border border-line bg-midnight px-3 py-2 text-sm" />
            </>
          ) : (
            <>
              <h2 className="flex items-center gap-2 text-xl font-bold">
                <ShieldCheck className="text-mission" size={20} /> Second factor
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                Enter the code from your authenticator app, or a recovery code.
              </p>
              <input autoFocus required value={code} onChange={(e) => setCode(e.target.value)}
                placeholder="000000" inputMode="numeric"
                className="telemetry mt-6 w-full rounded border border-line bg-midnight px-3 py-2.5 text-center !text-lg tracking-[0.4em]" />
              <button type="button" onClick={() => { setMfaToken(null); setCode(""); }}
                className="mt-2 text-xs text-ink-faint hover:text-ink">← back to password</button>
            </>
          )}
          {error && <p className="mt-3 text-sm text-critical">{error}</p>}
          <button disabled={busy}
            className="mt-6 w-full rounded bg-orbital text-on-accent py-2.5 text-sm font-semibold hover:bg-orbital-deep disabled:opacity-60">
            {busy ? "Authenticating…" : mfaToken ? "Verify" : "Access MissionOS"}
          </button>
          {!mfaToken && ssoAvailable && (
            <>
              <div className="my-4 flex items-center gap-3 text-[11px] uppercase tracking-wider text-ink-faint">
                <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
              </div>
              <button type="button" onClick={sso}
                className="w-full rounded border border-line py-2.5 text-sm font-semibold hover:border-orbital">
                Continue with organization SSO
              </button>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
