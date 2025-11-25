variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-north-1"  # Stockholm
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "test"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "cutcosts-testing"
}

variable "owner_email" {
  description = "Email of the resource owner"
  type        = string
}

variable "availability_zones" {
  description = "Availability zones to use"
  type        = list(string)
  default     = ["eu-north-1a", "eu-north-1b"]
}

# Batch control variables
variable "enable_batch_1" {
  description = "Enable Batch 1 resources (Core - $20/month)"
  type        = bool
  default     = true
}

variable "enable_batch_2" {
  description = "Enable Batch 2 resources (Advanced - $478/month)"
  type        = bool
  default     = false
}

variable "enable_batch_3" {
  description = "Enable Batch 3 resources (Data/Transfer - $378/month)"
  type        = bool
  default     = false
}

variable "enable_batch_4" {
  description = "Enable Batch 4 resources (Advanced Services - VPC Endpoint, Neptune, MSK, Redshift, VPN, Transit Gateway, ALB, Global Accelerator, DocumentDB - $1,166/month)"
  type        = bool
  default     = false
}

variable "enable_batch_5" {
  description = "Enable Batch 5 resources (Search/IaC - $700/month)"
  type        = bool
  default     = false
}
