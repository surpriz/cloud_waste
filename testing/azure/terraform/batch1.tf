# Batch 1: Core Azure Resources (~€68/month)
# These are the most common orphan resources for Azure testing

# 1. Managed Disk - Unattached (€1/month for 10GB Standard HDD)
resource "azurerm_managed_disk" "unattached" {
  count                = var.enable_batch_1 ? 1 : 0
  name                 = "${var.project_name}-unattached-disk"
  location             = azurerm_resource_group.main.location
  resource_group_name  = azurerm_resource_group.main.name
  storage_account_type = "Standard_LRS"
  create_option        = "Empty"
  disk_size_gb         = 10

  tags = {
    Name         = "${var.project_name}-unattached-disk"
    TestScenario = "Unattached Managed Disk"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# 2. Public IP Address - Unassociated (€3/month)
resource "azurerm_public_ip" "unassociated" {
  count               = var.enable_batch_1 ? 1 : 0
  name                = "${var.project_name}-unassociated-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = {
    Name         = "${var.project_name}-unassociated-pip"
    TestScenario = "Unassociated Public IP"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# 3. Virtual Machine - Stopped (€0/month when stopped, B1s size)
# Network Interface for VM
resource "azurerm_network_interface" "vm" {
  count               = var.enable_batch_1 ? 1 : 0
  name                = "${var.project_name}-vm-nic"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.public.id
    private_ip_address_allocation = "Dynamic"
  }

  tags = {
    Name        = "${var.project_name}-vm-nic"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_linux_virtual_machine" "stopped" {
  count               = var.enable_batch_1 ? 1 : 0
  name                = "${var.project_name}-stopped-vm"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  size                = "Standard_B1s"
  admin_username      = "azureuser"
  network_interface_ids = [
    azurerm_network_interface.vm[0].id,
  ]

  admin_ssh_key {
    username   = "azureuser"
    public_key = file("~/.ssh/id_rsa.pub")
  }

  os_disk {
    name                 = "${var.project_name}-vm-osdisk"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-focal"
    sku       = "20_04-lts"
    version   = "latest"
  }

  tags = {
    Name         = "${var.project_name}-stopped-vm"
    TestScenario = "Stopped Virtual Machine"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# Stop the VM immediately after creation
resource "null_resource" "stop_vm" {
  count = var.enable_batch_1 ? 1 : 0

  depends_on = [azurerm_linux_virtual_machine.stopped]

  provisioner "local-exec" {
    command = "az vm deallocate --resource-group ${azurerm_resource_group.main.name} --name ${azurerm_linux_virtual_machine.stopped[0].name}"
  }
}

# 4. Load Balancer - Zero traffic (€18/month for Standard SKU)
resource "azurerm_public_ip" "lb" {
  count               = var.enable_batch_1 ? 1 : 0
  name                = "${var.project_name}-lb-pip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = {
    Name        = "${var.project_name}-lb-pip"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_lb" "zero_traffic" {
  count               = var.enable_batch_1 ? 1 : 0
  name                = "${var.project_name}-zero-traffic-lb"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"

  frontend_ip_configuration {
    name                 = "PublicIPAddress"
    public_ip_address_id = azurerm_public_ip.lb[0].id
  }

  tags = {
    Name         = "${var.project_name}-zero-traffic-lb"
    TestScenario = "Load Balancer with Zero Traffic"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

resource "azurerm_lb_backend_address_pool" "zero_traffic" {
  count           = var.enable_batch_1 ? 1 : 0
  loadbalancer_id = azurerm_lb.zero_traffic[0].id
  name            = "${var.project_name}-backend-pool"
}

resource "azurerm_lb_probe" "zero_traffic" {
  count           = var.enable_batch_1 ? 1 : 0
  loadbalancer_id = azurerm_lb.zero_traffic[0].id
  name            = "http-probe"
  protocol        = "Http"
  request_path    = "/"
  port            = 80
}

# 5. Storage Account - Minimal usage (€1/month for Standard LRS)
resource "azurerm_storage_account" "minimal" {
  count                    = var.enable_batch_1 ? 1 : 0
  name                     = "${replace(var.project_name, "-", "")}storage"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = {
    Name         = "${var.project_name}-storage"
    TestScenario = "Storage Account with Minimal Usage"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}

# 6. ExpressRoute Circuit - 50 Mbps Local (€45/month)
resource "azurerm_express_route_circuit" "local" {
  count               = var.enable_batch_1 ? 1 : 0
  name                = "${var.project_name}-expressroute"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  service_provider_name = "Equinix"
  peering_location      = "Amsterdam"
  bandwidth_in_mbps     = 50

  sku {
    tier   = "Standard"
    family = "MeteredData"
  }

  tags = {
    Name         = "${var.project_name}-expressroute"
    TestScenario = "ExpressRoute Circuit with Zero Traffic"
    Environment  = var.environment
    Project      = var.project_name
    Owner        = var.owner_email
  }
}
