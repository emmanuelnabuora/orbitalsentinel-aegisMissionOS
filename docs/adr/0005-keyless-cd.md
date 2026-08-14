# ADR-0005: Keyless CD — OIDC role assumption, tag-driven releases, migrate-before-deploy

## Status
Accepted — Phase 4.

## Context
Long-lived cloud credentials in CI are the single most common root cause of
supply-chain compromise. A defense product's delivery chain will be examined
as part of procurement; it must be exemplary.

## Decision
1. **No AWS keys anywhere.** GitHub Actions authenticates via OIDC federation.
   The trust policy binds to this exact repository and only two subjects:
   `refs/tags/v*` (releases) and `refs/heads/main` (manual dispatch).
2. **Least-privilege deploy role.** Resource-scoped to: this ECR repo (push),
   this ECS service (update), the migrate task family (run-task, cluster-bound),
   the two task IAM roles (PassRole, service-bound), the web bucket, and the
   CloudFront distribution. `Describe*`/`RegisterTaskDefinition` are `*` only
   because AWS does not support resource-level scoping for them.
3. **Releases are tags.** `git tag v1.2.0 && git push --tags` is the release
   action. `concurrency: deploy-production` serializes deploys and never
   cancels one mid-flight. The `production` environment enables reviewer
   gates in GitHub when the team wants human approval.
4. **Migrate, then deploy.** The pipeline registers a migrate task revision
   with the new image, runs it as a one-off Fargate task, and hard-fails on a
   non-zero exit before any service update.

## Consequence: the backward-compatibility rule
Because old app tasks keep serving during (and after a failed) rollout,
**every migration must be compatible with the previous app version**:
expand-then-contract (add columns/tables now; drop or rename only after the
release that stopped using them ships). This is a code-review rule from today.

## Rollback
Deploy circuit breaker (ADR-0004) auto-rolls-back an unhealthy service update.
For a bad-but-healthy release: re-run CD from the previous tag. Schema
rollbacks are forward-only fixes (new migration), never `downgrade` in prod.
