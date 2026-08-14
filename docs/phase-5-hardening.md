# Phase 5 — Network & edge hardening

## Delivered
- **WAF** (`waf.tf`, us-east-1 provider alias as CLOUDFRONT scope requires):
  3 AWS managed rule groups + global and login-path rate rules, CloudWatch
  logging with credential-header redaction.
- **Origin cloaking**: ALB SG restricted to the CloudFront origin-facing
  prefix list; default-deny listeners forwarding only on the
  `X-Origin-Verify` secret stamped by our distribution.
- **Per-AZ NAT**: independent egress per AZ; `single_nat_gateway` toggle for
  dev stacks.

## Verified
All 14 Terraform files parse (HCL2). As with Phase 3: `terraform plan` needs
provider downloads unavailable in the build sandbox — plan locally before
apply. Expect the NAT change to *replace* private route tables; apply in a
maintenance window on existing stacks.

## Cost note
Second NAT gateway ≈ $33/mo + data. WAF ≈ $10/mo + $1/rule + per-request.
Both are appropriate for production; dev stacks can set
`single_nat_gateway = true` and skip nothing else.
