# Phase 2 — MVP: Full-stack AEGIS MissionOS

## Scope delivered

| Module | Backend | Frontend | Notes |
|---|---|---|---|
| Auth (login/refresh/RBAC) | ✅ | ✅ | Rotating refresh tokens, reuse detection, sessionStorage on web with silent refresh |
| Executive Dashboard | ✅ | ✅ | Assurance, threat level, quantum readiness, incidents, SentinelAI brief |
| Global Operations | ✅ | ✅ | Equirectangular ops grid; positions from asset `attributes.lat/lon` |
| Asset Inventory + Detail | ✅ | ✅ | Filters/search; detail shows profile, crypto records, threat history |
| Alerts Center | ✅ | ✅ | Severity/status filters, assignment, one-click status advance |
| Incident Investigations | ✅ | ✅ | Append-only timeline, notes, linked alerts, status workflow |
| SentinelAI | ✅ | ✅ | Chat + incident analysis; see provider architecture below |
| MissionIQ | ✅ | ✅ | Server-side explainable scoring + SVG dependency graph |
| QuantumShield | ✅ | ✅ | Crypto inventory, PQC readiness score, migration planner |
| Administration | ✅ | ✅ | User list (admin-gated; 403 handled honestly in UI) |
| Threat Intelligence, Reports | — | routed placeholder | Phase 3 |

## MissionIQ scoring (explainable by construction)
`score = 100 − Σ status_penalty(asset) × criticality_weight(link) − 6 × open_alerts × weight`,
clamped to [0,100]. Penalties: offline 45, degraded 22, unknown 10. Weights: critical 1.0,
high 0.75, medium 0.5, low 0.25. Every response carries `factors[]` — the exact deductions in
plain language. Health: ≥80 assured, ≥50 degraded, else at-risk. Fleet threat level derives from
open critical alerts. The formula is v1 and intentionally simple; it will be replaced by a
model-driven engine without changing the API contract.

## SentinelAI provider architecture
- `RuleBasedProvider` (`sentinel-rules-v1`, default): deterministic, data-grounded output built
  from live platform queries. Works with zero external dependencies; every claim traces to data.
- `AnthropicProvider`: activates when `ANTHROPIC_API_KEY` is set; refines the same grounded
  context. The provider never sees credentials or raw secrets.
- Every analysis writes an `ai_analysis` event to the incident timeline and an audit record —
  AI actions are attributable like human ones.

## QuantumShield classification
PQC-safe: ML-KEM, ML-DSA, SLH-DSA, FN-DSA, AES-256-GCM, CHACHA20-POLY1305.
Quantum-vulnerable: RSA, ECDSA, ECDH, DSA, DH, ED25519, X25519.
Readiness = % of records PQC-safe; recommendations generated per finding.

## Verification
- Backend: 34/34 tests (auth, RBAC, assets, missions, alerts, incidents, quantum, missioniq, sentinel), ruff clean.
- Frontend: strict tsc + production build clean.
- E2E smoke: migrated + seeded database, live uvicorn, verified login → fleet summary (avg 90,
  threat low) → quantum readiness (50, RSA/ECDSA flagged) → sentinel chat → mission graph.

## Demo quickstart
```bash
make up                      # postgres + redis + qdrant + api
cd apps/api && alembic upgrade head
AEGIS_ADMIN_EMAIL=you@example.com AEGIS_ADMIN_PASSWORD='<12+ chars>' python scripts/seed.py
cd ../web && npm install && npm run dev   # http://localhost:5173, proxies /api
```
