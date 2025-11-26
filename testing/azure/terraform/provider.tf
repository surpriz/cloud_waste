provider "azurerm" {
  features {}

  # Skip Resource Provider registration (already done manually)
  skip_provider_registration = true

  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id

  # Note: For creating resources, use your user account (az login)
  # For CutCosts scanning, use a Service Principal with Reader role
}
