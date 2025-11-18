terraform {
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Owner       = var.owner_email
      Purpose     = "CutCosts Testing Infrastructure"
    }
  }
}
