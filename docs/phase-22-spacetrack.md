# Phase 22 — Space-Track.org Integration

## What shipped

- `SpaceTrackClient` — session-cookie authentication (Space-Track has
  no API key; your account username/password is the credential),
  auto re-auth on session expiry, minimum-interval throttling on top of
  the client's own retry/backoff
- `poll_cdms()` — Conjunction Data Messages ingested into the exact
  same alert + auto-escalation pipeline as SOCRATES (Phase 18): CRITICAL
  + tracked asset -> incident, opened the same way, same tables
- `get_gp_by_catnrs()` — authoritative, batched (comma-delimited,
  never per-satellite) catalog lookups, available for future use
- Unit conversion at the parse boundary: CDM's meters/m-per-sec ->
  the platform's km/km-per-sec, so severity thresholds are source-agnostic

## Important: CDMs are operator-scoped, not a public feed

Space-Track's `cdm` class only returns messages for *your organization's
own registered spacecraft*. Unless the deploying customer is a
registered satellite operator with assets in Space-Track's system,
`poll_cdms()` will correctly return `(0, 0)` — SOCRATES remains the
general-purpose conjunction source for demos and customers without
their own registered fleet.

## Configure

```
SPACETRACK_USERNAME=you@example.com
SPACETRACK_PASSWORD=your-space-track-password
```

Both optional — omit them and ingestion runs exactly as before (SOCRATES
+ Celestrak + SWPC), no error, no degraded behavior.

## Verify

```
cd apps/api && python -m pytest tests/test_spacetrack.py -v   # 11 tests
```

11 tests cover: session login/retry/re-auth-on-401, bad-credential
handling, CDM parsing and unit conversion, the operator-gated empty
case, and full integration with the shared severity/escalation
pipeline — including proof that SOCRATES and Space-Track dedupe keys
for the same physical conjunction never collide.

## Data-source scoreboard

| Source | Status |
|---|---|
| Celestrak GP | ✅ live |
| NOAA SWPC | ✅ live |
| SOCRATES | ✅ live |
| Anthropic (SentinelAI) | ✅ live (pending your key/billing) |
| **Space-Track** | ✅ live (this phase; needs your account credentials) |
| UDL | ⏳ needs customer sponsorship |
