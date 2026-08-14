# ADR-0006: Edge hardening — WAF, origin cloaking, per-AZ NAT

## Status
Accepted — Phase 5.

## Decisions

### 1. WAFv2 on CloudFront
Managed rule groups (Common, KnownBadInputs, IPReputation) plus two rate
rules: a coarse 2000 req/5min/IP across the surface, and 100 req/5min/IP on
`/api/v1/auth/login`. Defense in depth with the app's Redis limiter
(10/5min per IP *and* per account): WAF absorbs volumetric abuse at the edge;
the app enforces the precise, account-aware budget. WAF logs go to CloudWatch
with `authorization` and `cookie` headers redacted — the log pipeline must
never become a credential store.

### 2. Origin cloaking (two independent layers)
A WAF is meaningless if the origin is directly reachable. Two layers close it:
- **Network**: the ALB security group admits only AWS's managed
  `cloudfront.origin-facing` prefix list — the general internet cannot open a
  TCP connection to the origin.
- **Application**: CloudFront stamps `X-Origin-Verify: <secret>` on origin
  requests; ALB listeners are default-deny (403) and forward only on header
  match. This closes the residual vector of *other* CloudFront distributions
  (which share the same origin-facing IPs). Secret lives in Secrets Manager;
  rotation is add-second-value-then-remove-old (documented in secrets.tf).

### 3. Per-AZ NAT gateways
One NAT per AZ with per-AZ private route tables (was: single shared NAT).
An AZ failure must not take out egress for healthy tasks in the surviving AZ.
`single_nat_gateway = true` remains available for cost-sensitive dev stacks.

## GovCloud note
CloudFront is not available in AWS GovCloud. For GovCloud/IL4+ deployments the
edge inverts: attach a REGIONAL WebACL directly to the ALB, drop origin
cloaking, and front with the agency's approved CDN/TIC egress. The Terraform
split (waf.tf/alb.tf) keeps that a contained change.
