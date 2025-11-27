# Batch 2: Advanced Azure Resources (~€71/month)
# These are advanced resources for comprehensive testing

# 1. Disk Snapshot - Orphaned (€2/month for 100GB)
# First create a temporary disk to snapshot, then delete it
resource "azurerm_managed_disk" "snapshot_source" {
  count                = var.enable_batch_2 ? 1 : 0
  name                 = "${var.project_name}-snapshot-source-disk"
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  storage_account_type = "Standard_LRS"
  create_option        = "Empty"
  disk_size_gb         = 100

  tags = {
    Name        = "${var.project_name}-snapshot-source-disk"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_snapshot" "orphaned" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-orphaned-snapshot"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  create_option       = "Copy"
  source_uri          = azurerm_managed_disk.snapshot_source[0].id

  tags = {
    Name         = "${var.project_name}-orphaned-snapshot"
    TestScenario = "Orphaned Disk Snapshot (source disk deleted)"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }

  depends_on = [azurerm_managed_disk.snapshot_source]
}

# Delete the source disk after snapshot creation to make it orphaned
resource "null_resource" "delete_snapshot_source" {
  count = var.enable_batch_2 ? 1 : 0

  depends_on = [azurerm_snapshot.orphaned]

  provisioner "local-exec" {
    command = "az disk delete --resource-group ${azurerm_resource_group.main.name} --name ${azurerm_managed_disk.snapshot_source[0].name} --yes"
  }
}

# 2. NAT Gateway - No subnet attached (€35/month)
resource "azurerm_public_ip" "nat_gateway" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-nat-gateway-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = {
    Name        = "${var.project_name}-nat-gateway-pip"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_nat_gateway" "no_subnet" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-nat-gateway"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Standard"

  tags = {
    Name         = "${var.project_name}-nat-gateway"
    TestScenario = "NAT Gateway without subnet attachment"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

resource "azurerm_nat_gateway_public_ip_association" "nat_gateway" {
  count                = var.enable_batch_2 ? 1 : 0
  nat_gateway_id       = azurerm_nat_gateway.no_subnet[0].id
  public_ip_address_id = azurerm_public_ip.nat_gateway[0].id
}

# 3. Azure SQL Database - Basic tier, stopped (€4/month)
resource "azurerm_mssql_server" "test" {
  count                        = var.enable_batch_2 ? 1 : 0
  name                         = "${var.project_name}-sql-server"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = "P@ssw0rd1234!" # Test only
  minimum_tls_version          = "1.2"

  tags = {
    Name        = "${var.project_name}-sql-server"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_mssql_database" "stopped" {
  count      = var.enable_batch_2 ? 1 : 0
  name       = "${var.project_name}-sql-database"
  server_id  = azurerm_mssql_server.test[0].id
  sku_name   = "Basic"
  collation  = "SQL_Latin1_General_CP1_CI_AS"
  max_size_gb = 2

  tags = {
    Name         = "${var.project_name}-sql-database"
    TestScenario = "Azure SQL Database - Stopped/Idle"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# 4. AKS Cluster - 1 node, minimal workload (€30/month)
resource "azurerm_kubernetes_cluster" "test" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-aks"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = "${var.project_name}-aks"

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_B2s"
    vnet_subnet_id = azurerm_subnet.private.id
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    service_cidr      = "10.2.0.0/16"
    dns_service_ip    = "10.2.0.10"
  }

  tags = {
    Name         = "${var.project_name}-aks"
    TestScenario = "AKS Cluster - Minimal workload"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# 5. Function App - Consumption plan, zero executions (€0/month pay-per-execution)
resource "azurerm_service_plan" "consumption" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-function-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption plan

  tags = {
    Name        = "${var.project_name}-function-plan"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_storage_account" "function_app" {
  count                    = var.enable_batch_2 ? 1 : 0
  name                     = "${replace(var.project_name, "-", "")}funcapp"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = {
    Name        = "${var.project_name}-function-app-storage"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_linux_function_app" "test" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-function-app"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  storage_account_name       = azurerm_storage_account.function_app[0].name
  storage_account_access_key = azurerm_storage_account.function_app[0].primary_access_key
  service_plan_id            = azurerm_service_plan.consumption[0].id

  site_config {
    application_stack {
      node_version = "18"
    }
  }

  tags = {
    Name         = "${var.project_name}-function-app"
    TestScenario = "Function App - Zero executions"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# 6. Cosmos DB - Table API, serverless (€0/month pay-per-request)
resource "azurerm_cosmosdb_account" "test" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "${var.project_name}-cosmos-db"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  automatic_failover_enabled = false

  consistency_policy {
    consistency_level       = "Session"
    max_interval_in_seconds = 5
    max_staleness_prefix    = 100
  }

  geo_location {
    location          = azurerm_resource_group.main.location
    failover_priority = 0
  }

  capabilities {
    name = "EnableServerless"
  }

  capabilities {
    name = "EnableTable"
  }

  tags = {
    Name         = "${var.project_name}-cosmos-db"
    TestScenario = "Cosmos DB Table API - Zero requests"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

resource "azurerm_cosmosdb_table" "test" {
  count               = var.enable_batch_2 ? 1 : 0
  name                = "testtable"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.test[0].name
}
