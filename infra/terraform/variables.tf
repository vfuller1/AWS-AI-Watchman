variable "aws_region" {
  description = "AWS Region where Watchman resources are deployed."
  type = string
  default = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name."
  type = string
  default = "dev"
}

variable "project_name" {
  description = "Project prefix used for naming AWS resources."
  type = string
  default = "aws-ai-watchman"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for orchestration logs."
  type = number
  default = 90
}

variable "orchestrator_service_principal" {
  description = "AWS service principal that can assume the orchestration role."
  type = string
  default = "lambda.amazonaws.com"
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type = map(string)
  default = {}
}


