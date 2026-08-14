# ADR-0002: Phase 0 security baseline

Status: accepted · Date: 2026-07-09

## Decisions
1. **Argon2id** for password hashing — memory-hard, current OWASP default.
2. **HS256 JWTs, 15-minute TTL** for Phase 0. Verification enforces an
   explicit algorithm allow-list, issuer, and required claims (`exp`, `iat`,
   `sub`, `iss`). Asymmetric signing (RS256/EdDSA) plus refresh rotation and
   revocation via Redis `jti` denylist arrive with the Phase 1 auth service —
   HS256 is acceptable only while a single service verifies tokens.
3. **Fail-fast config**: settings are typed and validated at boot; staging and
   production refuse to start with a development secret key.
4. **Headers-by-default**: nosniff, DENY framing, no-referrer, no-store, and a
   restrictive Permissions-Policy on every response via middleware, so no
   route can forget them.
5. **Docs off outside local/test** to reduce reconnaissance surface.

## Non-goals (Phase 0)
mTLS between services, KMS-backed secret management, FedRAMP/IL controls
mapping — tracked for the deployment phase.
