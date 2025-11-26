# Resource Group
# All Azure resources must be created within a Resource Group

resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-rg"
  location = var.azure_region

  tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Owner       = var.owner_email
    Purpose     = "CutCosts Testing Infrastructure"
  }
}

# Virtual Network and Networking Infrastructure
# This provides the base networking for all test resources

resource "azurerm_virtual_network" "main" {
  name                = "${var.project_name}-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  tags = {
    Name        = "${var.project_name}-vnet"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

resource "azurerm_subnet" "public" {
  name                 = "${var.project_name}-public-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_subnet" "private" {
  name                 = "${var.project_name}-private-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.10.0/24"]
}

# Network Security Group (equivalent to AWS Security Group)
resource "azurerm_network_security_group" "default" {
  name                = "${var.project_name}-default-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "allow-internal-vnet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "10.0.0.0/16"
    destination_address_prefix = "10.0.0.0/16"
  }

  tags = {
    Name        = "${var.project_name}-default-nsg"
    Environment = var.environment
    Project     = var.project_name
    Owner       = var.owner_email
  }
}

# Associate NSG with subnets
resource "azurerm_subnet_network_security_group_association" "public" {
  subnet_id                 = azurerm_subnet.public.id
  network_security_group_id = azurerm_network_security_group.default.id
}

resource "azurerm_subnet_network_security_group_association" "private" {
  subnet_id                 = azurerm_subnet.private.id
  network_security_group_id = azurerm_network_security_group.default.id
}
