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
      values   = [
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
  statement {
    effect = "Allow"
    actions = [
      "ec2:Describe*",
      "iam:Get*",
      "iam:List*",
      "kms:Describe*",
      "kms:List*",
      "logs:Describe*",
      "logs:Get*",
      "logs:List*",
      "s3:List*",
      "sts:GetCallerIdentity",
      "dynamodb:Describe*",
      "dynamodb:List*",
      "cloudwatch:Describe*",
      "cloudwatch:Get*",
      "cloudwatch:List*",
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "cloudformation:*",
      "dynamodb:*",
      "iam:*",
      "kms:*",
      "lambda:*",
      "logs:*",
      "sns:*",
      "s3:*",
      "cloudwatch:*",
      "events:*",
      "tag:*",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name   = "${var.project_name}-${var.environment}-github-actions-deploy"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.github_actions_deploy_permissions.json
}
