data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [data.tls_certificate.github_actions.certificates[0].sha1_fingerprint]

  tags = local.common_tags
}

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/${var.github_branch}",
        "repo:${var.github_repository}:pull_request",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "${var.project_name}-${var.environment}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "github_actions_deploy_permissions" {
  # Read-only across all services needed for plan
  statement {
    sid    = "ReadOnlyForPlan"
    effect = "Allow"
    actions = [
      "iam:Get*",
      "iam:List*",
      "kms:Describe*",
      "kms:List*",
      "kms:GetKeyPolicy",
      "kms:GetKeyRotationStatus",
      "logs:Describe*",
      "logs:Get*",
      "logs:List*",
      "s3:List*",
      "s3:GetBucket*",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:GetReplicationConfiguration",
      "sts:GetCallerIdentity",
      "dynamodb:Describe*",
      "dynamodb:List*",
      "sns:Get*",
      "sns:List*",
    ]
    resources = ["*"]
  }

  # Write permissions scoped to project-prefixed resources
  statement {
    sid    = "WriteForApply"
    effect = "Allow"
    actions = [
      "dynamodb:*",
      "iam:*",
      "kms:*",
      "logs:*",
      "sns:*",
      "s3:*",
      "cloudwatch:*",
      "tag:*",
    ]
    resources = ["*"]

    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/Project"
      values   = [var.project_name]
    }
  }

  # OIDC provider management (no resource tag on IAM OIDC providers)
  statement {
    sid    = "OidcProviderManagement"
    effect = "Allow"
    actions = [
      "iam:CreateOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider",
      "iam:GetOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
      "iam:TagOpenIDConnectProvider",
      "iam:UntagOpenIDConnectProvider",
      "iam:ListOpenIDConnectProviders",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name   = "${var.project_name}-${var.environment}-github-actions-deploy"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.github_actions_deploy_permissions.json
}
