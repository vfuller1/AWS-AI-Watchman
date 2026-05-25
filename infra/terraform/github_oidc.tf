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
        "repo:${var.github_repository}:environment:aws-deploy",
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

  # Glue — resource tags are not supported on all create actions
  statement {
    sid    = "GlueManagement"
    effect = "Allow"
    actions = [
      "glue:CreateDatabase",
      "glue:DeleteDatabase",
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:UpdateDatabase",
      "glue:TagResource",
      "glue:UntagResource",
      "glue:GetTags",
      "glue:CreateCrawler",
      "glue:DeleteCrawler",
      "glue:GetCrawler",
      "glue:GetCrawlers",
      "glue:UpdateCrawler",
      "glue:StartCrawler",
      "glue:StopCrawler",
    ]
    resources = ["*"]
  }

  # Lambda — needed to create/update the Bronze router function
  statement {
    sid    = "LambdaManagement"
    effect = "Allow"
    actions = [
      "lambda:CreateFunction",
      "lambda:DeleteFunction",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:AddPermission",
      "lambda:RemovePermission",
      "lambda:GetPolicy",
      "lambda:ListFunctions",
      "lambda:TagResource",
      "lambda:UntagResource",
      "lambda:ListTags",
    ]
    resources = ["*"]
  }

  # S3 bucket notifications (used to wire Bronze bucket → Lambda)
  statement {
    sid    = "S3NotificationManagement"
    effect = "Allow"
    actions = [
      "s3:GetBucketNotification",
      "s3:PutBucketNotification",
    ]
    resources = ["*"]
  }

  # Bedrock Guardrails and Knowledge Base management
  statement {
    sid    = "BedrockManagement"
    effect = "Allow"
    actions = [
      "bedrock:CreateGuardrail",
      "bedrock:UpdateGuardrail",
      "bedrock:DeleteGuardrail",
      "bedrock:GetGuardrail",
      "bedrock:ListGuardrails",
      "bedrock:CreateGuardrailVersion",
      "bedrock:UpdateGuardrailVersion",
      "bedrock:DeleteGuardrailVersion",
      "bedrock:GetGuardrailVersion",
      "bedrock:ListGuardrailVersions",
      "bedrock:CreateKnowledgeBase",
      "bedrock:UpdateKnowledgeBase",
      "bedrock:DeleteKnowledgeBase",
      "bedrock:GetKnowledgeBase",
      "bedrock:ListKnowledgeBases",
      "bedrock:CreateDataSource",
      "bedrock:UpdateDataSource",
      "bedrock:DeleteDataSource",
      "bedrock:GetDataSource",
      "bedrock:ListDataSources",
      "bedrock:TagResource",
      "bedrock:UntagResource",
      "bedrock:ListTagsForResource",
    ]
    resources = ["*"]
  }

  # OpenSearch Serverless — required when enable_bedrock_kb=true
  statement {
    sid    = "OpenSearchServerlessManagement"
    effect = "Allow"
    actions = [
      "aoss:CreateCollection",
      "aoss:UpdateCollection",
      "aoss:DeleteCollection",
      "aoss:BatchGetCollection",
      "aoss:ListCollections",
      "aoss:CreateSecurityPolicy",
      "aoss:UpdateSecurityPolicy",
      "aoss:DeleteSecurityPolicy",
      "aoss:GetSecurityPolicy",
      "aoss:ListSecurityPolicies",
      "aoss:CreateAccessPolicy",
      "aoss:UpdateAccessPolicy",
      "aoss:DeleteAccessPolicy",
      "aoss:GetAccessPolicy",
      "aoss:ListAccessPolicies",
      "aoss:TagResource",
      "aoss:UntagResource",
      "aoss:ListTagsForResource",
      "aoss:APIAccessAll",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name   = "${var.project_name}-${var.environment}-github-actions-deploy"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.github_actions_deploy_permissions.json
}
