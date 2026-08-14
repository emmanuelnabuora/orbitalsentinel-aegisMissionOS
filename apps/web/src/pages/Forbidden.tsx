import { Link } from "react-router-dom";
import { ShieldOff } from "lucide-react";

export default function Forbidden() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <div className="max-w-sm text-center">
        <ShieldOff size={32} className="mx-auto mb-4 text-amber" strokeWidth={1.5} />
        <h1 className="mb-2 text-lg font-semibold">You don't have access to this area</h1>
        <p className="mb-6 text-sm text-ink-muted">
          Your role doesn't include this module. If you need it, ask your
          organization admin to update your workspace role.
        </p>
        <Link to="/" className="rounded bg-orbital text-on-accent px-4 py-2 text-sm font-medium">
          Back to my workspace
        </Link>
      </div>
    </div>
  );
}
