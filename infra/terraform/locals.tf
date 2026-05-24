locals {
  common_tags = merge(
    {
      Project = var.project_name
      Environment = var.environment
      ManagedBy = "Terraform"
      Component = "watchman-foundation"
    },
    var.tags
  )
}

