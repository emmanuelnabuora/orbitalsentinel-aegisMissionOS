# Phase 3 — Production deployment

## Verified in this phase
- Full test suite (37) passes on **both** sqlite and **PostgreSQL 16** —
  conftest honors `TEST_DATABASE_URL`; CI now runs both, plus a migration
  up/down/up cycle on Postgres.
- Seed is idempotent on Postgres (run twice, one dataset).
- Live E2E on Postgres + Redis: login 200; brute force → `401×N` then `429`
  with per-IP and per-account Redis counters.
- All 12 Terraform files parse (HCL2). `terraform validate`/`plan` require
  provider downloads unavailable in the build sandbox — run locally before apply.

## New in this phase
- **Login rate limiting** (`core/ratelimit.py`): Redis fixed-window,
  `AEGIS_LOGIN_RATE_LIMIT` (10) per `AEGIS_LOGIN_RATE_WINDOW` (300s), enforced
  per source IP and per target account. 429 with generic message (no oracle).
- **Web container**: multi-stage Node→nginx-unprivileged, SPA fallback,
  `/api` proxy via `API_UPSTREAM` template var. `docker compose up` now brings
  up the entire product at http://localhost:3000.
- **infrastructure/terraform**: VPC (2 AZ, public/private), ALB, ECS Fargate
  (api service + one-off migrate task), RDS, ElastiCache, ECR, Secrets Manager,
  S3+CloudFront. See ADR-0004.

## Deploy runbook (first environment)
```bash
cd infrastructure/terraform
# 0. One-time: create the S3 state bucket + DynamoDB lock table, then
#    uncomment the backend block in versions.tf.
terraform init
terraform apply -var api_image=placeholder -target aws_ecr_repository.api

# 1. Build & push the API image
aws ecr get-login-password | docker login --username AWS --password-stdin <ecr-url>
docker build -t <ecr-url>:$(git rev-parse --short HEAD) apps/api
docker push <ecr-url>:$(git rev-parse --short HEAD)

# 2. Full apply
terraform apply -var api_image=<ecr-url>:<sha> -var acm_certificate_arn=<arn>

# 3. Migrate, then verify service health
aws ecs run-task --cluster aegis-prod --task-definition aegis-prod-migrate \
  --launch-type FARGATE --network-configuration '<private subnets + api SG>'

# 4. Publish the SPA
cd apps/web && npm ci && npm run build
aws s3 sync dist "s3://$(terraform output -raw web_bucket)" --delete
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"

# 5. Seed the first admin (one-off task, same pattern as migrate, command:
#    ["python", "scripts/seed.py"] with AEGIS_ADMIN_* env)
```

## Not yet done (deliberately)
- WAF on CloudFront/ALB; per-AZ NAT; container image signing; OIDC deploy
  role for GitHub Actions (CD). These are the next infra increments.
