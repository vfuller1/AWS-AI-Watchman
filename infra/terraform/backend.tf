terraform {
  backend "s3" {
    bucket         = "aws-ai-watchman-dev-tfstate"
    key            = "terraform/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "aws-ai-watchman-dev-tfstate-lock"
    encrypt        = true
  }
}
