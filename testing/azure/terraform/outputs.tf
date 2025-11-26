# Resource Group Outputs
output "resource_group_name" {
  description = "Resource Group name"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Resource Group location"
  value       = azurerm_resource_group.main.location
}

# Virtual Network Outputs
output "vnet_id" {
  description = "Virtual Network ID"
  value       = azurerm_virtual_network.main.id
}

output "public_subnet_id" {
  description = "Public subnet ID"
  value       = azurerm_subnet.public.id
}

output "private_subnet_id" {
  description = "Private subnet ID"
  value       = azurerm_subnet.private.id
}

output "nsg_id" {
  description = "Network Security Group ID"
  value       = azurerm_network_security_group.default.id
}

# Batch 1 Outputs
output "batch_1_resources" {
  description = "Batch 1 resource IDs and names"
  value = var.enable_batch_1 ? {
    managed_disk_id        = try(azurerm_managed_disk.unattached[0].id, null)
    public_ip_address      = try(azurerm_public_ip.unassociated[0].ip_address, null)
    vm_id                  = try(azurerm_linux_virtual_machine.stopped[0].id, null)
    vm_name                = try(azurerm_linux_virtual_machine.stopped[0].name, null)
    load_balancer_id       = try(azurerm_lb.zero_traffic[0].id, null)
    storage_account_name   = try(azurerm_storage_account.minimal[0].name, null)
    expressroute_circuit_id = try(azurerm_express_route_circuit.local[0].id, null)
  } : null
}

# Batch 2 Outputs
output "batch_2_resources" {
  description = "Batch 2 resource IDs and names"
  value = var.enable_batch_2 ? {
    # Will be populated when batch2.tf is created
  } : null
}

# Batch 3 Outputs
output "batch_3_resources" {
  description = "Batch 3 resource IDs and names"
  value = var.enable_batch_3 ? {
    # Will be populated when batch3.tf is created
  } : null
}

# Cost Estimation
output "estimated_monthly_cost" {
  description = "Estimated monthly cost in EUR"
  value = {
    batch_1 = var.enable_batch_1 ? 68 : 0
    batch_2 = var.enable_batch_2 ? 0 : 0
    batch_3 = var.enable_batch_3 ? 0 : 0
    total   = (var.enable_batch_1 ? 68 : 0) + (var.enable_batch_2 ? 0 : 0) + (var.enable_batch_3 ? 0 : 0)
  }
}

# Detailed Cost Breakdown (Batch 1)
output "batch_1_cost_breakdown" {
  description = "Detailed monthly cost breakdown for Batch 1 in EUR"
  value = var.enable_batch_1 ? {
    managed_disk        = 1
    public_ip          = 3
    virtual_machine    = 0  # €0 when stopped/deallocated
    load_balancer      = 18
    storage_account    = 1
    expressroute_circuit = 45
    total              = 68
  } : null
}
