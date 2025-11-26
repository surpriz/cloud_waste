variable "azure_subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "azure_tenant_id" {
  description = "Azure Tenant ID"
  type        = string
}

variable "azure_region" {
  description = "Azure region for resources"
  type        = string
  default     = "westeurope"  # West Europe
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

# Batch control variables
variable "enable_batch_1" {
  description = "Enable Batch 1 resources (Core - €68/month)"
  type        = bool
  default     = true
}

variable "enable_batch_2" {
  description = "Enable Batch 2 resources (Advanced - TBD)"
  type        = bool
  default     = false
}

variable "enable_batch_3" {
  description = "Enable Batch 3 resources (Premium - TBD)"
  type        = bool
  default     = false
}
