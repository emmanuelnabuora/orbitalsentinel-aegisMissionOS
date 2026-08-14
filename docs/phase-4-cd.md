# Phase 4 — Continuous deployment

## Release flow
```
git tag v0.2.0 && git push --tags
  └─ CD: test gate (Postgres) → build+push image (:gitsha)
     → register migrate taskdef → run one-off migration (fail = stop)
     → deploy ECS service (waits for stability; circuit breaker rolls back)
     → build SPA → S3 sync → CloudFront invalidation
```

## One-time wiring after `terraform apply`
Set GitHub **repository variables** from Terraform outputs:

| Variable | Terraform output |
|---|---|
| `AWS_REGION` | `var.region` |
| `AWS_DEPLOY_ROLE_ARN` | `deploy_role_arn` |
| `ECR_REPOSITORY_URL` | `ecr_repository_url` |
| `ECS_CLUSTER` | `ecs_cluster_name` |
| `ECS_SERVICE` | `ecs_service_name` |
| `MIGRATE_TASK_FAMILY` | `migrate_task_definition` |
| `PRIVATE_SUBNET_IDS` | `private_subnet_ids` |
| `API_SECURITY_GROUP_ID` | `api_security_group_id` |
| `WEB_BUCKET` | `web_bucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `cloudfront_distribution_id` |

Optionally add required reviewers to the `production` environment for a
human approval gate.

## Verified in this phase
- `actionlint` clean on both workflows; YAML parses.
- Deploy IAM policy and OIDC trust parse (HCL2) and are resource-scoped per
  ADR-0005 (documented exceptions where AWS lacks resource-level support).

## Team rule introduced
Migrations must be **expand-then-contract** (backward compatible with the
previous release) — enforced in code review; see ADR-0005 for why.
