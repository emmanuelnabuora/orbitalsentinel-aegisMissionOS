import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "@/lib/api";

export default function SSOCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");
    if (!code || !state) { setError("Missing SSO parameters"); return; }
    api.ssoCallback(code, state)
      .then(() => navigate("/"))
      .catch((e) => setError(e instanceof ApiError ? e.message : "SSO sign-in failed"));
  }, [params, navigate]);

  return (
    <div className="grid min-h-screen place-items-center">
      {error ? (
        <div className="text-center">
          <p className="text-critical">{error}</p>
          <button onClick={() => navigate("/login")}
            className="mt-4 rounded border border-line px-4 py-2 text-sm hover:border-orbital">
            Back to sign in
          </button>
        </div>
      ) : (
        <p className="telemetry text-ink-muted">COMPLETING SSO SIGN-IN…</p>
      )}
    </div>
  );
}
