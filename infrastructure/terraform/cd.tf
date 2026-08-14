# Keyless CD: GitHub Actions assumes a scoped role via OIDC (ADR-0005).
# No long-lived AWS keys exist anywhere in the delivery chain.

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  # GitHub's root CAs; AWS now validates against its own trust store and
  # treats this as a required-but-unused field.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/tags/v*",   # releases
        "repo:${var.github_repository}:ref:refs/heads/main" # manual dispatch
      ]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name_prefix        = "${local.name}-deploy-"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage", "ecr:PutImage",
      "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
    ]
    resources = [aws_ecr_repository.api.arn]
  }
  statement {
    sid = "EcsRead"
    actions = [
      "ecs:DescribeTaskDefinition", "ecs:DescribeServices",
      "ecs:DescribeTasks", "ecs:ListTasks",
    ]
    resources = ["*"] # Describe* does not support resource-level scoping
  }
  statement {
    sid       = "EcsRegister"
    actions   = ["ecs:RegisterTaskDefinition", "ecs:TagResource"]
    resources = ["*"] # RegisterTaskDefinition does not support resource-level scoping
  }
  statement {
    sid       = "EcsDeploy"
    actions   = ["ecs:UpdateService"]
    resources = [aws_ecs_service.api.id]
  }
  statement {
    sid       = "EcsMigrate"
    actions   = ["ecs:RunTask"]
    resources = ["arn:aws:ecs:${var.region}:*:task-definition/${local.name}-migrate:*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }
  statement {
    sid       = "PassTaskRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
  statement {
    sid       = "WebSync"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.web.arn]
  }
  statement {
    sid       = "WebObjects"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]
  }
  statement {
    sid       = "CdnInvalidate"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [aws_cloudfront_distribution.web.arn]
  }
}

resource "aws_iam_role_policy" "deploy" {
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
