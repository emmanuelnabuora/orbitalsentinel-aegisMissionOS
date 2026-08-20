# AEGIS MissionOS — Incident Response Runbook

**Status:** Draft — internal, not yet exercised. Review before relying on it in a live incident.
**Owners:** Emmanuel Nakitare, Nelson Kigen, Haggai Mudenyo.
**Scope note:** Laban Kiplagat is excluded from this rotation and from any incident touching CUI-adjacent systems, consistent with his exclusion from the SBIR proposal on U.S.-performance-of-R&D grounds.

---

## 1. Reporting obligation — read this first

If an incident involves **covered defense information (CDI)** or affects a system on which CDI resides or transits, **DFARS 252.204-7012 requires reporting to DoD within 72 hours of discovery**, via [dibnet.dod.mil](https://dibnet.dod.mil).

This is a contractual clock, not a best-practice suggestion — it starts at discovery, not at confirmation, and not at "once we understand root cause."

**Action before this is ever needed:** obtain a DoD-issued medium assurance certificate now. It cannot be issued same-day during an active incident, and without it the 72-hour clock cannot practically be met.

Once award and CUI-handling begin, the platform's CMMC Level 1 self-assessment / DFARS 252.204-7012 obligations mean any CUI-affecting incident must also be reflected in the SSP/POA&M — not resolved and forgotten.

---

## 2. On-call & authority

| Role | Primary | Backup |
|---|---|---|
| Incident Commander (declares, coordinates, owns the DIBNet report) | Emmanuel | Nelson |
| Technical lead (containment/eradication) | Haggai | Nelson |
| Comms (customer/Government notification, internal updates) | Emmanuel | — |

Any founder can **declare** an incident. Only the Incident Commander (or backup) authorizes containment actions that cause downtime or data loss (e.g., platform-wide re-auth, DB rollback).

---

## 3. Incident classes and first response

### 3.1 Credential / account compromise
**Signals:** anomalous login pattern, MFA reset outside expected flow, rate-limit trips in `structlog` output, user-reported unrecognized session.

**First response (fastest containment lever already built into the platform):**
1. Revoke the affected token family — this invalidates the compromised refresh token and every access token derived from it, even ones already issued (`apps/api/src/aegis_api/core/security.py`).
2. Force password reset + MFA re-enrollment for the affected account.
3. Query audit log for actions taken under that session before revocation.
4. If the account had elevated (admin) scope: review the ABAC/RBAC audit trail for permission or role changes made during the compromise window, since those don't get undone by token revocation alone.

### 3.2 Dependency vulnerability (CVE in a direct or transitive package)
**Signals:** CI security-audit workflow failure (`.github/workflows/security-audit.yml`), GitHub Dependabot/security advisory, manual `pip-audit`/`npm audit` finding.

**First response:**
1. Confirm exploitability in this codebase specifically — a CVE in an unused code path (e.g., a dev-server-only Vite vulnerability) is lower urgency than one in a reachable production dependency.
2. Patch and re-run the full CI suite, not just the audit job — dependency bumps have broken things before.
3. If the vulnerable version was ever deployed to a live environment, check whether the vulnerability class (e.g., path traversal, RCE) could have been exploited in that window; this determines whether it escalates to a reportable incident under §1.

### 3.3 Data ingestion source compromise / spoofing
**Signals:** Space-Track, SOCRATES, Celestrak, or NOAA SWPC returning data that fails validation, unexpected schema, or conjunction alerts inconsistent with independently known orbital data.

**First response:**
1. The ingestion layer's fail-open semantics (ADR-0004 lineage) mean a bad source degrades gracefully rather than blocking the platform — confirm this behaved as designed rather than assuming silence means "fine."
2. Isolate the specific connector (ports-and-adapters architecture allows disabling one source without affecting others).
3. Do not re-enable until the source's own status/incident channel confirms the anomaly's cause.

### 3.4 Infrastructure / cloud compromise
**Signals:** unexpected Terraform state drift, unrecognized IAM activity, anomalous RDS/network traffic.

**First response:**
1. Keyless OIDC CI/CD means there are no long-lived deploy credentials to rotate — confirm no static credentials were introduced outside that pattern (that itself would be a finding).
2. Rotate `AEGIS_SECRET_KEY` and force platform-wide re-authentication if session integrity is in question.
3. Review security-group and IAM changes against Terraform state — the zero-trust tier design (ALB → API → RDS, each admitting only its upstream tier) means lateral movement should be visibly abnormal if it occurred.

---

## 4. Standard flow (NIST SP 800-61 phases)

1. **Preparation** — this document, the DIBNet cert, the CI security-audit workflow, on-call rotation above.
2. **Identification** — `structlog` centralized logging; confirm auth failures, MFA resets, and rate-limit trips are actually being captured with enough context to reconstruct a timeline (verify this — don't assume).
3. **Containment** — class-specific steps in §3. When in doubt, favor the token-revocation / connector-isolation levers that already exist over broader shutdowns.
4. **Eradication** — patch, rotate, rebuild from clean state as needed.
5. **Recovery** — staged re-enablement, monitoring for recurrence before declaring closed.
6. **Post-incident** — written summary (facts, timeline, root cause, what changed), filed even for near-misses. Update this runbook if the incident revealed a gap in it.

---

## 5. Open items (fill in before this is exercise-ready)

- [ ] DoD medium assurance certificate — not yet obtained.
- [ ] Confirm `structlog` output is actually shipped somewhere durable/queryable during an incident (not just stdout in a container that may be gone).
- [ ] Tabletop exercise — this runbook has not been tested against a simulated incident.
- [ ] Customer/Government notification templates — not yet drafted.
