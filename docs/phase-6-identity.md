# Phase 6 — Identity: MFA + SSO

## Delivered
- **TOTP MFA**: setup (QR SVG + manual secret) → activate → challenge login →
  verify (TOTP or one-time recovery code) → disable. Encrypted seeds,
  purpose-isolated challenge tokens, limiter on the verify endpoint.
- **OIDC SSO**: `/auth/sso/{status,begin,callback}` — PKCE, nonce, JWKS
  validation, optional least-privilege auto-provisioning. Configure with
  `AEGIS_OIDC_ISSUER / _CLIENT_ID / _CLIENT_SECRET / _REDIRECT_URL`
  (+ `_AUTO_PROVISION`). Works with Okta, Entra ID, Keycloak, login.gov.
- **UI**: two-step login with SSO button (appears only when configured),
  `/sso/callback` landing, Account Security page (enroll, recovery codes
  shown once, disable) linked from the top bar.

## Verified
- 45/45 tests on sqlite **and** PostgreSQL 16 (incl. 5 MFA, 4 stub-IdP SSO).
- Live HTTP E2E on Postgres+Redis, 11 steps: enroll → challenge → wrong code
  401 → verify 200 → challenge-token-as-credential 401 → recovery code 200 →
  recovery replay 401 → disable 204.
- Migration up/down/up on Postgres **and** newest-migration-over-seeded-data
  (the check that caught the missing server_default).
- Frontend strict TS build clean.
