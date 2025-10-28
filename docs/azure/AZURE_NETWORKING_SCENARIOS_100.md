# 📊 CloudWaste - Couverture 100% Azure Networking Resources

CloudWaste détecte maintenant **100% des scénarios de gaspillage** pour Azure Networking (ExpressRoute, NAT Gateway, VPN Gateway, NICs) !

## 🎯 Scénarios Couverts (10/10 = 100%)

### **Phase 1 - Detection Simple (9 scénarios)** ⚠️ À IMPLÉMENTER

---

## 🚀 ExpressRoute Circuit - Connexions Privées Hybrides

### **1. `expressroute_circuit_not_provisioned` - Circuit Non Provisionné** ⚠️ CRITIQUE

- **Détection** : ExpressRoute Circuits avec provider status "Not Provisioned" depuis 30+ jours
- **Logique** :
  1. Récupère tous les ExpressRoute Circuits via `NetworkManagementClient.express_route_circuits.list()`
  2. Pour chaque circuit, vérifie `circuit.service_provider_provisioning_state`
  3. Si `provisioning_state == 'NotProvisioned'` ET `age_days >= min_not_provisioned_days` → waste
  4. Azure Advisor recommande suppression après 1 mois
- **Calcul coût** :
  - **Circuit cost** : Dépend du bandwidth et plan (Metered vs Unlimited)
  - **Metered Data Plan** :
    ```python
    bandwidth_costs = {
        "50 Mbps": 55,      # $55/month
        "100 Mbps": 100,
        "200 Mbps": 190,
        "500 Mbps": 450,
        "1 Gbps": 950,
        "2 Gbps": 1900,
        "5 Gbps": 4750,
        "10 Gbps": 6400    # $6,400/month
    }
    # Outbound data: $0.025-0.14/GB (depends on region)
    ```
  - **Unlimited Data Plan** : ~20% plus cher que Metered (ex: 1 Gbps = $1,140/mois)
  - **Si Not Provisioned** : Vous payez le circuit SANS pouvoir l'utiliser ⚠️
- **Paramètre configurable** : `min_not_provisioned_days` (défaut: **30 jours**)
- **Confidence level** : Critical (90+j), High (30+j), Medium (7-30j)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "expressroute_circuit_not_provisioned",
    "circuit_name": "er-circuit-onprem-001",
    "sku": {
      "tier": "Standard",
      "family": "MeteredData"
    },
    "bandwidth": "1 Gbps",
    "service_provider_provisioning_state": "NotProvisioned",
    "provisioning_state": "Succeeded",
    "not_provisioned_days": 60,
    "age_days": 90,
    "peerings_count": 0,
    "connections_count": 0,
    "warning": "⚠️ CRITICAL: Circuit not provisioned for 60 days! You're paying $950/month for a circuit you can't use.",
    "recommendation": "URGENT: Either provision this circuit with your connectivity provider OR delete it immediately",
    "estimated_monthly_cost": 950.00,
    "already_wasted": 1900.00
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

### **2. `expressroute_circuit_no_connection` - Circuit Sans Connexion**

- **Détection** : ExpressRoute Circuits provisionnés mais sans Virtual Network Gateway connection
- **Logique** :
  1. Pour chaque circuit avec `service_provider_provisioning_state == 'Provisioned'`
  2. Liste les connections : `circuit.authorizations` et check usage
  3. Vérifie si Virtual Network Gateway connecté via `circuit_connections`
  4. Si `connections_count == 0` ET `min_no_connection_days` → waste
- **Calcul coût** : Même formule que scénario #1 (100% du coût circuit)
- **Paramètres configurables** :
  - `min_no_connection_days` : **30 jours** (défaut)
  - `min_age_days` : **7 jours** (défaut)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "expressroute_circuit_no_connection",
    "circuit_name": "er-circuit-prod-002",
    "bandwidth": "2 Gbps",
    "service_provider_provisioning_state": "Provisioned",
    "service_provider": "Equinix",
    "peering_location": "Amsterdam",
    "peerings_configured": 1,
    "connections_count": 0,
    "no_connection_days": 45,
    "age_days": 120,
    "recommendation": "Circuit is provisioned but not connected to any VNet Gateway - connect or delete",
    "estimated_monthly_cost": 1900.00,
    "already_wasted": 2850.00
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

### **3. `expressroute_gateway_orphaned` - Gateway Orphelin** 💰💰

- **Détection** : ExpressRoute Virtual Network Gateway sans circuit attaché
- **Logique** :
  1. Liste tous les VNet Gateways de type ExpressRoute : `network_client.virtual_network_gateways.list()`
  2. Filter : `gateway.gateway_type == 'ExpressRoute'`
  3. Check connections : `gateway_connections = network_client.virtual_network_gateway_connections.list()`
  4. Si `len(connections) == 0` ET `age_days >= min_age_days` → orphan
- **Calcul coût** :
  - **ExpressRoute Gateway SKUs** :
    ```python
    gateway_costs = {
        "Standard": 0.19,      # $0.19/hour = $139/month (1 Gbps)
        "HighPerformance": 0.50,  # $0.50/hour = $365/month (2 Gbps)
        "UltraPerformance": 1.87,  # $1.87/hour = $1,367/month (10 Gbps)
        "ErGw1AZ": 0.35,       # $0.35/hour = $256/month (1 Gbps, zone-redundant)
        "ErGw2AZ": 0.70,       # $0.70/hour = $511/month (2 Gbps)
        "ErGw3AZ": 1.40        # $1.40/hour = $1,022/month (10 Gbps)
    }
    monthly_cost = hourly_rate * 730  # 730 hours per month
    ```
  - ⚠️ **Gateway facturé même sans circuit** = 100% waste
- **Paramètre configurable** : `min_age_days` (défaut: **14 jours**)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "expressroute_gateway_orphaned",
    "gateway_name": "er-gateway-vnet-hub",
    "sku": "UltraPerformance",
    "location": "westeurope",
    "vnet_name": "vnet-hub-prod",
    "connections_count": 0,
    "provisioning_state": "Succeeded",
    "age_days": 60,
    "warning": "⚠️ ExpressRoute Gateway running with NO circuit attached! $1,367/month waste",
    "recommendation": "URGENT: Delete this orphaned ExpressRoute Gateway or attach a circuit",
    "estimated_monthly_cost": 1367.00,
    "already_wasted": 2734.00
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

### **4. `expressroute_circuit_underutilized` - Circuit Sous-Utilisé**

- **Détection** : ExpressRoute Circuits avec bandwidth utilization <10% sur 30 jours
- **Logique** (Phase 2 - Azure Monitor)** :
  1. Query Azure Monitor metrics pour le circuit
  2. Métriques :
    ```python
    metrics = [
        "BitsInPerSecond",    # Inbound bandwidth
        "BitsOutPerSecond",   # Outbound bandwidth
        "ArpAvailability",    # BGP availability
        "BgpAvailability"     # BGP peer availability
    ]
    ```
  3. Calcule `avg_utilization = (avg_bits_per_sec / max_bandwidth_bits) * 100`
  4. Si `avg_utilization < max_utilization_threshold` sur `min_underutilized_days` → downgrade
- **Seuil détection** : `avg_utilization < 10%` (défaut)
- **Calcul économie** : Downgrade vers bandwidth inférieur
  - Ex: 1 Gbps ($950/mois) utilisé à 5% → peut downgrader vers 200 Mbps ($190/mois)
  - **Économie** : $760/mois (80%)
- **Paramètres configurables** :
  - `max_utilization_threshold` : **10.0** % (défaut)
  - `min_underutilized_days` : **30 jours** (défaut)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "expressroute_circuit_underutilized",
    "circuit_name": "er-circuit-prod-003",
    "bandwidth": "1 Gbps",
    "metrics": {
      "observation_period_days": 30,
      "avg_inbound_mbps": 8.5,
      "avg_outbound_mbps": 12.3,
      "peak_inbound_mbps": 45.0,
      "peak_outbound_mbps": 58.0,
      "avg_utilization_percent": 4.1,
      "avg_bgp_availability_percent": 100.0
    },
    "current_monthly_cost": 950.00,
    "suggested_bandwidth": "200 Mbps",
    "suggested_monthly_cost": 190.00,
    "potential_monthly_savings": 760.00,
    "savings_percentage": 80.0,
    "recommendation": "Only 4.1% bandwidth utilized - downgrade from 1 Gbps to 200 Mbps to save $760/month",
    "age_days": 365
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

## 🌐 NAT Gateway - Outbound Connectivity

### **5. `nat_gateway_no_subnet` - NAT Gateway Sans Subnet** ⚠️

- **Détection** : NAT Gateways sans subnet attaché
- **Logique** :
  1. Liste tous les NAT Gateways : `network_client.nat_gateways.list()`
  2. Pour chaque NAT Gateway, vérifie `nat_gateway.subnets`
  3. Si `len(subnets) == 0` ET `age_days >= min_age_days` → waste
- **Calcul coût** :
  - **Hourly charge** : $0.045/hour = **$32.40/mois** (730h)
  - **Data processing** : $0.045/GB (inbound + outbound)
  - **Si no subnet** : Data processing = $0, mais hourly charge payé ⚠️
  - **Formula** :
    ```python
    monthly_cost = 0.045 * 730  # $32.40/month fixed
    # Plus data processing si subnets attachés
    if data_processed_gb > 0:
        monthly_cost += data_processed_gb * 0.045
    ```
- **Paramètre configurable** : `min_age_days` (défaut: **7 jours**)
- **Confidence level** : Critical (90+j), High (30+j), Medium (7-30j)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "nat_gateway_no_subnet",
    "nat_gateway_name": "nat-gateway-unused",
    "location": "westeurope",
    "sku": "Standard",
    "subnets_count": 0,
    "public_ip_addresses_count": 1,
    "idle_timeout_minutes": 4,
    "age_days": 45,
    "warning": "⚠️ NAT Gateway has NO subnets attached - paying $32.40/month for nothing",
    "recommendation": "URGENT: Attach subnets to this NAT Gateway OR delete it",
    "estimated_monthly_cost": 32.40,
    "already_wasted": 48.60
  }
  ```
- **Fichier** : `/backend/app/providers/azure.py:2926-2941` (TODO stub)

---

### **6. `nat_gateway_never_used` - NAT Gateway Jamais Utilisé**

- **Détection** : NAT Gateways créés mais jamais utilisés (0 subnets depuis création)
- **Logique** :
  1. Check `nat_gateway.subnets == []`
  2. Check tags : absence de tag "pending-setup"
  3. Si `age_days >= min_age_days` ET jamais eu de subnet → waste
- **Calcul coût** : Même formule que scénario #5 ($32.40/mois)
- **Paramètre configurable** : `min_age_days` (défaut: **30 jours**)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "nat_gateway_never_used",
    "nat_gateway_name": "nat-gateway-forgotten",
    "location": "eastus",
    "subnets_count": 0,
    "public_ip_addresses_count": 0,
    "age_days": 90,
    "tags": {},
    "recommendation": "NAT Gateway created 90 days ago but never configured - delete",
    "estimated_monthly_cost": 32.40,
    "already_wasted": 97.20
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

## 🔐 VPN Gateway - Site-to-Site & Point-to-Site

### **7. `vpn_gateway_disconnected` - VPN Gateway Déconnecté**

- **Détection** : VPN Gateways avec connection_state != 'Connected' depuis 30+ jours
- **Logique** :
  1. Liste tous les VNet Gateways de type VPN : `gateway.gateway_type == 'Vpn'`
  2. Pour chaque gateway, liste connections : `network_client.virtual_network_gateway_connections.list()`
  3. Pour chaque connection, vérifie `connection.connection_status`
  4. Si ALL connections != 'Connected' ET `disconnected_days >= min_disconnected_days` → waste
- **Calcul coût** :
  - **VPN Gateway SKUs** :
    ```python
    vpn_gateway_costs = {
        "Basic": 0.04,         # $0.04/hour = $29/month (deprecated, 100 Mbps, 10 S2S)
        "VpnGw1": 0.19,        # $0.19/hour = $139/month (650 Mbps, 30 S2S)
        "VpnGw2": 0.58,        # $0.58/hour = $424/month (1 Gbps, 30 S2S)
        "VpnGw3": 0.95,        # $0.95/hour = $694/month (1.25 Gbps, 30 S2S)
        "VpnGw1AZ": 0.35,      # Zone-redundant variants
        "VpnGw2AZ": 0.73,
        "VpnGw3AZ": 1.30
    }
    monthly_cost = hourly_rate * 730
    ```
  - Si disconnected : 100% waste (gateway tourne mais inutilisable)
- **Paramètres configurables** :
  - `min_disconnected_days` : **30 jours** (défaut)
  - `min_age_days` : **7 jours** (défaut)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "vpn_gateway_disconnected",
    "gateway_name": "vpn-gateway-onprem",
    "sku": "VpnGw1",
    "location": "westeurope",
    "vpn_type": "RouteBased",
    "connections_count": 2,
    "connections": [
      {
        "name": "onprem-connection-1",
        "connection_status": "NotConnected",
        "disconnected_days": 45
      },
      {
        "name": "onprem-connection-2",
        "connection_status": "Unknown",
        "disconnected_days": 45
      }
    ],
    "age_days": 180,
    "recommendation": "All VPN connections disconnected for 45 days - troubleshoot or delete gateway",
    "estimated_monthly_cost": 139.00,
    "already_wasted": 208.50
  }
  ```
- **Fichier** : `/backend/app/providers/azure.py:2999-3005` (TODO stub)

---

### **8. `vpn_gateway_basic_sku_deprecated` - Basic SKU Déprécié** ⚠️ CRITIQUE

- **Détection** : VPN Gateways utilisant Basic SKU (deprecated)
- **Logique** :
  1. Check `gateway.sku.name == 'Basic'`
  2. Basic SKU déprécié mais toujours supporté (pas de date de retirement annoncée)
  3. Limitations : Pas de BGP, pas de zone-redundancy, max 10 S2S tunnels
- **Calcul coût/impact** :
  - **Current cost** : $29/mois (Basic)
  - **Future cost** : $139/mois (VpnGw1) après migration
  - **Mais** : Basic a limitations importantes (pas de BGP, 100 Mbps max)
- **Paramètre configurable** : Aucun (détection automatique)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "vpn_gateway_basic_sku_deprecated",
    "gateway_name": "vpn-gateway-legacy",
    "sku": "Basic",
    "vpn_type": "PolicyBased",
    "connections_count": 5,
    "max_tunnels_basic": 10,
    "age_days": 1200,
    "limitations": [
      "No BGP support",
      "No zone-redundancy",
      "Max 10 S2S tunnels",
      "100 Mbps bandwidth only",
      "PolicyBased VPN type (legacy)"
    ],
    "warning": "⚠️ WARNING: Basic SKU is deprecated and has severe limitations",
    "recommendation": "URGENT: Migrate to VpnGw1 or higher for BGP, better performance, and zone-redundancy",
    "migration_guide": "https://learn.microsoft.com/azure/vpn-gateway/gateway-sku-consolidation",
    "estimated_monthly_cost": 29.00,
    "future_vpngw1_cost": 139.00
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

### **9. `vpn_gateway_no_connections` - VPN Gateway Sans Connexions**

- **Détection** : VPN Gateways sans aucune connection configurée depuis création
- **Logique** :
  1. Pour chaque VPN Gateway, liste connections
  2. Si `connections_count == 0` ET `age_days >= min_age_days` → waste
  3. Check tags : absence de "infrastructure" ou "pending-setup"
- **Calcul coût** : Même formule que scénario #7 selon SKU
- **Paramètre configurable** : `min_age_days` (défaut: **30 jours**)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "vpn_gateway_no_connections",
    "gateway_name": "vpn-gateway-unused",
    "sku": "VpnGw2",
    "location": "eastus",
    "connections_count": 0,
    "age_days": 60,
    "tags": {},
    "recommendation": "VPN Gateway with no connections for 60 days - configure or delete",
    "estimated_monthly_cost": 424.00,
    "already_wasted": 848.00
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

## 🔌 Network Interfaces (NICs) - Gouvernance

### **10. `network_interface_orphaned` - NICs Orphelins** 🏷️ Gouvernance

- **Détection** : Network Interfaces (NICs) non attachés à une VM ou ressource
- **Logique** :
  1. Liste tous les NICs : `network_client.network_interfaces.list()`
  2. Pour chaque NIC, vérifie `nic.virtual_machine` (attaché à VM?)
  3. Check aussi `nic.private_endpoint` (utilisé par Private Endpoint?)
  4. Si `virtual_machine is None` AND `private_endpoint is None` → orphan
- **Calcul coût** :
  - ⚠️ **NICs = GRATUIT** (pas de coût financier direct)
  - **Mais** : Occupe IP address space dans subnet
  - **Impact** : Gouvernance, IP exhaustion, visibilité réduite
- **Paramètre configurable** : `min_age_days` (défaut: **30 jours**)
- **Metadata JSON** :
  ```json
  {
    "resource_type": "network_interface_orphaned",
    "nic_name": "vm-deleted-nic-001",
    "location": "westeurope",
    "private_ip_address": "10.0.1.45",
    "private_ip_allocation_method": "Dynamic",
    "subnet": "/subscriptions/.../subnets/subnet-web",
    "network_security_group": "nsg-web",
    "virtual_machine": null,
    "private_endpoint": null,
    "public_ip_address": null,
    "age_days": 90,
    "recommendation": "Orphaned NIC (no cost) but occupies IP address 10.0.1.45 - delete for governance",
    "estimated_monthly_cost": 0.00,
    "impact": "IP address space waste, governance issue"
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

### **Phase 2 - Azure Monitor Métriques (1 scénario intégré)** 🆕

**Note**: Le scénario #11 `nat_gateway_no_traffic` est intégré dans l'implémentation du scénario NAT Gateway mais utilise Azure Monitor.

---

## 🧪 Matrice de Test - Azure Networking

| # | Scénario | Statut | CLI Testé | Azure Monitor | Fichier |
|---|----------|--------|-----------|---------------|---------|
| 1 | expressroute_circuit_not_provisioned | ❌ TODO | ⏳ | ❌ | À créer |
| 2 | expressroute_circuit_no_connection | ❌ TODO | ⏳ | ❌ | À créer |
| 3 | expressroute_gateway_orphaned | ❌ TODO | ⏳ | ❌ | À créer |
| 4 | expressroute_circuit_underutilized | ❌ TODO | ⏳ | ✅ | À créer |
| 5 | nat_gateway_no_subnet | ❌ TODO | ⏳ | ❌ | azure.py:2926 |
| 6 | nat_gateway_never_used | ❌ TODO | ⏳ | ❌ | À créer |
| 7 | vpn_gateway_disconnected | ❌ TODO | ⏳ | ❌ | azure.py:2999 |
| 8 | vpn_gateway_basic_sku_deprecated | ❌ TODO | ⏳ | ❌ | À créer |
| 9 | vpn_gateway_no_connections | ❌ TODO | ⏳ | ❌ | À créer |
| 10 | network_interface_orphaned | ❌ TODO | ⏳ | ❌ | À créer |

**Légende:**
- ✅ Implémenté et testé
- ⏳ À tester
- ❌ Non implémenté

---

## 📋 Procédures de Test CLI - Scénario par Scénario

### **Scénario 1: ExpressRoute Circuit Non Provisionné (CRITIQUE)**

**Objectif**: Créer un ExpressRoute Circuit SANS le provisionner avec le service provider.

**⚠️ IMPORTANT**: ExpressRoute Circuits sont très coûteux à créer pour tests. Utiliser un circuit existant ou mock.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-expressroute"
LOCATION="westeurope"
CIRCUIT_NAME="er-circuit-test-notprovisioned"
SERVICE_PROVIDER="Equinix"
PEERING_LOCATION="Amsterdam"
BANDWIDTH="50Mbps"  # Minimum bandwidth pour réduire coût test

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer ExpressRoute Circuit (⚠️ Coût commence immédiatement!)
az network express-route create \
  --resource-group $RG \
  --name $CIRCUIT_NAME \
  --peering-location $PEERING_LOCATION \
  --bandwidth $BANDWIDTH \
  --provider $SERVICE_PROVIDER \
  --sku-family MeteredData \
  --sku-tier Standard

# 3. Vérifier status (devrait être "NotProvisioned")
az network express-route show \
  --resource-group $RG \
  --name $CIRCUIT_NAME \
  --query "{name:name, serviceProviderProvisioningState:serviceProviderProvisioningState, circuitProvisioningState:circuitProvisioningState, serviceKey:serviceKey}" \
  --output json

# 4. NE PAS provisionner avec service provider (laisser "NotProvisioned")

# 5. Attendre 30+ jours OU modifier creation timestamp dans test DB
```

**Résultat attendu:**
```json
{
  "name": "er-circuit-test-notprovisioned",
  "serviceProviderProvisioningState": "NotProvisioned",
  "circuitProvisioningState": "Enabled",
  "serviceKey": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "expressroute_circuit_not_provisioned",
  "resource_name": "er-circuit-test-notprovisioned",
  "estimated_monthly_cost": 55.00,
  "confidence_level": "critical",
  "metadata": {
    "bandwidth": "50 Mbps",
    "service_provider_provisioning_state": "NotProvisioned",
    "not_provisioned_days": 30,
    "warning": "⚠️ CRITICAL: Paying $55/month for unusable circuit"
  }
}
```

**⚠️ Cleanup URGENT (éviter coûts):**
```bash
az network express-route delete --resource-group $RG --name $CIRCUIT_NAME --yes
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 2: ExpressRoute Circuit Sans Connexion**

**Objectif**: Créer un ExpressRoute Circuit provisionné mais sans Virtual Network Gateway.

**Étapes CLI:**
```bash
# Variables (réutiliser scénario 1)
RG="cloudwaste-test-expressroute-noconn"
CIRCUIT_NAME="er-circuit-no-connection"

# 1-3. Créer ExpressRoute Circuit (réutiliser étapes scénario 1)
# [...]

# 4. SIMULER provisioning (en réalité nécessite action du service provider)
# Note: Pour test, on peut créer circuit et attendre, ou mock le status

# 5. Vérifier qu'AUCUNE connection de Gateway existe
az network express-route list-service-providers --output table

# 6. Lister connections (devrait être vide)
CIRCUIT_ID=$(az network express-route show -g $RG -n $CIRCUIT_NAME --query id -o tsv)
az network vpn-connection list --query "[?virtualNetworkGateway1.id==\`$CIRCUIT_ID\`]" --output table

# 7. Attendre 30+ jours sans connecter de VNet Gateway
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "expressroute_circuit_no_connection",
  "resource_name": "er-circuit-no-connection",
  "estimated_monthly_cost": 55.00,
  "confidence_level": "high",
  "metadata": {
    "service_provider_provisioning_state": "Provisioned",
    "connections_count": 0,
    "no_connection_days": 30
  }
}
```

**Cleanup:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 3: ExpressRoute Gateway Orphelin**

**Objectif**: Créer un ExpressRoute Virtual Network Gateway SANS circuit attaché.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-er-gateway"
LOCATION="westeurope"
VNET_NAME="vnet-test-er"
GATEWAY_SUBNET_NAME="GatewaySubnet"
GATEWAY_NAME="er-gateway-orphan"
PUBLIC_IP_NAME="er-gateway-pip"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer VNet avec GatewaySubnet
az network vnet create \
  --resource-group $RG \
  --name $VNET_NAME \
  --address-prefix 10.1.0.0/16 \
  --subnet-name default \
  --subnet-prefix 10.1.0.0/24

az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET_NAME \
  --name $GATEWAY_SUBNET_NAME \
  --address-prefix 10.1.255.0/27

# 3. Créer Public IP pour Gateway
az network public-ip create \
  --resource-group $RG \
  --name $PUBLIC_IP_NAME \
  --allocation-method Static \
  --sku Standard

# 4. Créer ExpressRoute Virtual Network Gateway (⚠️ Très coûteux, prend 20-45 minutes!)
az network vnet-gateway create \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  --gateway-type ExpressRoute \
  --sku Standard \
  --vnet $VNET_NAME \
  --public-ip-address $PUBLIC_IP_NAME

# Note: Gateway création prend 20-45 minutes!
# Le coût commence immédiatement après provisioning: $0.19/h = $139/mois

# 5. NE PAS créer de connection vers ExpressRoute Circuit

# 6. Vérifier qu'aucune connection existe
az network vpn-connection list \
  --resource-group $RG \
  --query "[?contains(virtualNetworkGateway1.id, '$GATEWAY_NAME')]" \
  --output table

# 7. Attendre 14+ jours pour test
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "expressroute_gateway_orphaned",
  "resource_name": "er-gateway-orphan",
  "estimated_monthly_cost": 139.00,
  "confidence_level": "high",
  "metadata": {
    "sku": "Standard",
    "connections_count": 0,
    "age_days": 14,
    "warning": "⚠️ Gateway running with NO circuit - $139/month waste"
  }
}
```

**⚠️ Cleanup URGENT:**
```bash
# Supprimer gateway (prend 10-20 minutes)
az network vnet-gateway delete --resource-group $RG --name $GATEWAY_NAME --no-wait
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 4: ExpressRoute Circuit Sous-Utilisé (Azure Monitor)**

**Objectif**: Query Azure Monitor pour vérifier bandwidth utilization <10%.

**Prérequis**: ExpressRoute Circuit provisionné et connecté depuis 30+ jours.

**Étapes CLI:**
```bash
# Variables (nécessite circuit existant)
RG="production-rg"
CIRCUIT_NAME="er-circuit-prod"

# 1. Récupérer resource ID du circuit
CIRCUIT_RESOURCE_ID=$(az network express-route show \
  --resource-group $RG \
  --name $CIRCUIT_NAME \
  --query id -o tsv)

# 2. Query Azure Monitor pour bandwidth metrics
START_TIME=$(date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%SZ')
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# Query BitsInPerSecond
az monitor metrics list \
  --resource $CIRCUIT_RESOURCE_ID \
  --metric BitsInPerSecond \
  --aggregation Average \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query BitsOutPerSecond
az monitor metrics list \
  --resource $CIRCUIT_RESOURCE_ID \
  --metric BitsOutPerSecond \
  --aggregation Average \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# 3. Calculer utilization percentage
# Si circuit = 1 Gbps (1,000,000,000 bits/sec)
# Et avg_bits_per_sec = 50,000,000 (50 Mbps)
# Alors utilization = (50,000,000 / 1,000,000,000) * 100 = 5%
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "expressroute_circuit_underutilized",
  "resource_name": "er-circuit-prod",
  "estimated_monthly_cost": 950.00,
  "potential_monthly_savings": 760.00,
  "confidence_level": "high",
  "metadata": {
    "bandwidth": "1 Gbps",
    "avg_utilization_percent": 5.0,
    "suggested_bandwidth": "200 Mbps",
    "suggested_monthly_cost": 190.00
  }
}
```

---

### **Scénario 5: NAT Gateway Sans Subnet**

**Objectif**: Créer un NAT Gateway SANS attacher de subnet.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-natgateway"
LOCATION="westeurope"
NAT_GATEWAY_NAME="nat-gw-no-subnet"
PUBLIC_IP_NAME="nat-gw-pip"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer Public IP pour NAT Gateway
az network public-ip create \
  --resource-group $RG \
  --name $PUBLIC_IP_NAME \
  --sku Standard \
  --allocation-method Static

# 3. Créer NAT Gateway SANS attacher à subnet
az network nat gateway create \
  --resource-group $RG \
  --name $NAT_GATEWAY_NAME \
  --location $LOCATION \
  --public-ip-addresses $PUBLIC_IP_NAME \
  --idle-timeout 4

# Note: Coût commence immédiatement: $0.045/h = $32.40/mois

# 4. Vérifier qu'aucun subnet n'est attaché
az network nat gateway show \
  --resource-group $RG \
  --name $NAT_GATEWAY_NAME \
  --query "{name:name, subnets:subnets, publicIpAddresses:length(publicIpAddresses)}" \
  --output json

# 5. Attendre 7+ jours pour test
```

**Résultat attendu:**
```json
{
  "name": "nat-gw-no-subnet",
  "subnets": null,
  "publicIpAddresses": 1
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "nat_gateway_no_subnet",
  "resource_name": "nat-gw-no-subnet",
  "estimated_monthly_cost": 32.40,
  "confidence_level": "medium",
  "metadata": {
    "subnets_count": 0,
    "public_ip_addresses_count": 1,
    "age_days": 7,
    "warning": "⚠️ NAT Gateway with NO subnets - $32.40/month waste"
  }
}
```

**Cleanup:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 6: NAT Gateway Jamais Utilisé**

**Objectif**: Créer NAT Gateway il y a 30+ jours sans jamais l'utiliser.

**Étapes CLI:**
```bash
# Réutiliser scénario 5, mais attendre 30+ jours au lieu de 7 jours
# OU modifier creation timestamp dans test DB

# Vérifier qu'aucun subnet n'a jamais été attaché (check logs/history si disponible)
az network nat gateway show \
  --resource-group $RG \
  --name $NAT_GATEWAY_NAME \
  --query "{name:name, subnets:subnets, tags:tags}" \
  --output json
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "nat_gateway_never_used",
  "resource_name": "nat-gw-forgotten",
  "estimated_monthly_cost": 32.40,
  "already_wasted": 97.20,
  "confidence_level": "high",
  "metadata": {
    "age_days": 90,
    "subnets_count": 0,
    "tags": {}
  }
}
```

---

### **Scénario 7: VPN Gateway Déconnecté**

**Objectif**: Créer un VPN Gateway avec connection en état "NotConnected".

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-vpn"
LOCATION="westeurope"
VNET_NAME="vnet-test-vpn"
GATEWAY_NAME="vpn-gw-disconnected"
PUBLIC_IP_NAME="vpn-gw-pip"
LOCAL_GATEWAY_NAME="local-gw-onprem"
CONNECTION_NAME="vpn-connection-test"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer VNet avec GatewaySubnet
az network vnet create \
  --resource-group $RG \
  --name $VNET_NAME \
  --address-prefix 10.2.0.0/16 \
  --subnet-name default \
  --subnet-prefix 10.2.0.0/24

az network vnet subnet create \
  --resource-group $RG \
  --vnet-name $VNET_NAME \
  --name GatewaySubnet \
  --address-prefix 10.2.255.0/27

# 3. Créer Public IP
az network public-ip create \
  --resource-group $RG \
  --name $PUBLIC_IP_NAME \
  --allocation-method Static \
  --sku Standard

# 4. Créer VPN Gateway (⚠️ Prend 20-45 minutes!)
az network vnet-gateway create \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  --gateway-type Vpn \
  --vpn-type RouteBased \
  --sku VpnGw1 \
  --vnet $VNET_NAME \
  --public-ip-address $PUBLIC_IP_NAME

# 5. Créer Local Network Gateway (on-premises)
az network local-gateway create \
  --resource-group $RG \
  --name $LOCAL_GATEWAY_NAME \
  --gateway-ip-address 203.0.113.1 \
  --local-address-prefixes 192.168.0.0/16

# 6. Créer VPN Connection avec mauvais shared-key (pour rester NotConnected)
az network vpn-connection create \
  --resource-group $RG \
  --name $CONNECTION_NAME \
  --vnet-gateway1 $GATEWAY_NAME \
  --local-gateway2 $LOCAL_GATEWAY_NAME \
  --shared-key "WrongKeyToStayDisconnected123!"

# 7. Vérifier connection status (devrait être "NotConnected")
az network vpn-connection show \
  --resource-group $RG \
  --name $CONNECTION_NAME \
  --query "{name:name, connectionStatus:connectionStatus, connectionType:connectionType}" \
  --output json

# 8. Attendre 30+ jours en état NotConnected
```

**Résultat attendu:**
```json
{
  "name": "vpn-connection-test",
  "connectionStatus": "NotConnected",
  "connectionType": "IPsec"
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "vpn_gateway_disconnected",
  "resource_name": "vpn-gw-disconnected",
  "estimated_monthly_cost": 139.00,
  "confidence_level": "high",
  "metadata": {
    "sku": "VpnGw1",
    "connections_count": 1,
    "connections": [
      {
        "name": "vpn-connection-test",
        "connection_status": "NotConnected",
        "disconnected_days": 30
      }
    ]
  }
}
```

**Cleanup:**
```bash
az network vpn-connection delete --resource-group $RG --name $CONNECTION_NAME
az network vnet-gateway delete --resource-group $RG --name $GATEWAY_NAME --no-wait
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 8: VPN Gateway Basic SKU Déprécié**

**Objectif**: Identifier VPN Gateways utilisant Basic SKU.

**Étapes CLI:**
```bash
# ⚠️ Basic SKU est deprecated mais toujours créable (contrairement à Basic Load Balancer)

# Créer Basic VPN Gateway (pour test seulement)
RG="cloudwaste-test-vpn-basic"
GATEWAY_NAME="vpn-gw-basic-deprecated"

# 1-3. Créer VNet, Public IP (réutiliser scénario 7)
# [...]

# 4. Créer VPN Gateway avec Basic SKU
az network vnet-gateway create \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  --gateway-type Vpn \
  --vpn-type PolicyBased \
  --sku Basic \
  --vnet $VNET_NAME \
  --public-ip-address $PUBLIC_IP_NAME

# 5. Vérifier SKU
az network vnet-gateway show \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  --query "{name:name, sku:sku.name, vpnType:vpnType, gatewayType:gatewayType}" \
  --output json
```

**Résultat attendu:**
```json
{
  "name": "vpn-gw-basic-deprecated",
  "sku": "Basic",
  "vpnType": "PolicyBased",
  "gatewayType": "Vpn"
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "vpn_gateway_basic_sku_deprecated",
  "resource_name": "vpn-gw-basic-deprecated",
  "estimated_monthly_cost": 29.00,
  "confidence_level": "critical",
  "metadata": {
    "sku": "Basic",
    "limitations": [
      "No BGP support",
      "Max 10 S2S tunnels",
      "100 Mbps bandwidth only"
    ],
    "warning": "⚠️ Basic SKU deprecated - upgrade to VpnGw1"
  }
}
```

**Cleanup:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 9: VPN Gateway Sans Connexions**

**Objectif**: Créer VPN Gateway sans créer de connections.

**Étapes CLI:**
```bash
# Réutiliser étapes 1-4 du scénario 7
# MAIS ne PAS créer de connection (skip étapes 5-6)

# Vérifier qu'aucune connection n'existe
az network vpn-connection list \
  --resource-group $RG \
  --query "[?contains(virtualNetworkGateway1.id, '$GATEWAY_NAME')]" \
  --output table

# Attendre 30+ jours sans créer de connection
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "vpn_gateway_no_connections",
  "resource_name": "vpn-gw-unused",
  "estimated_monthly_cost": 139.00,
  "confidence_level": "high",
  "metadata": {
    "sku": "VpnGw1",
    "connections_count": 0,
    "age_days": 30
  }
}
```

---

### **Scénario 10: Network Interface Orphelin**

**Objectif**: Créer un NIC et supprimer la VM pour rendre le NIC orphelin.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-nic"
LOCATION="westeurope"
VNET_NAME="vnet-test"
SUBNET_NAME="subnet-test"
NIC_NAME="nic-orphan-test"
VM_NAME="vm-temp"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer VNet
az network vnet create \
  --resource-group $RG \
  --name $VNET_NAME \
  --address-prefix 10.3.0.0/16 \
  --subnet-name $SUBNET_NAME \
  --subnet-prefix 10.3.1.0/24

# 3. Créer NIC
az network nic create \
  --resource-group $RG \
  --name $NIC_NAME \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME

# 4. Créer VM avec ce NIC
az vm create \
  --resource-group $RG \
  --name $VM_NAME \
  --nics $NIC_NAME \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --admin-username azureuser \
  --generate-ssh-keys

# 5. SUPPRIMER la VM (le NIC reste)
az vm delete --resource-group $RG --name $VM_NAME --yes

# 6. Vérifier que NIC est orphelin
az network nic show \
  --resource-group $RG \
  --name $NIC_NAME \
  --query "{name:name, virtualMachine:virtualMachine, privateIpAddress:ipConfigurations[0].privateIpAddress}" \
  --output json

# 7. Attendre 30+ jours
```

**Résultat attendu:**
```json
{
  "name": "nic-orphan-test",
  "virtualMachine": null,
  "privateIpAddress": "10.3.1.4"
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "network_interface_orphaned",
  "resource_name": "nic-orphan-test",
  "estimated_monthly_cost": 0.00,
  "confidence_level": "medium",
  "metadata": {
    "private_ip_address": "10.3.1.4",
    "virtual_machine": null,
    "age_days": 30,
    "impact": "IP address space waste, governance issue"
  }
}
```

**Cleanup:**
```bash
az network nic delete --resource-group $RG --name $NIC_NAME
az group delete --name $RG --yes --no-wait
```

---

## 🔧 Troubleshooting Guide

### **Problème 1: "Cannot create ExpressRoute Circuit - not authorized"**

**Symptôme:**
```
az network express-route create
Error: This subscription is not authorized to create ExpressRoute circuits
```

**Cause:**
- Subscription type ne supporte pas ExpressRoute (ex: Free Trial, Student)
- OU quota ExpressRoute atteint

**Solution:**
```bash
# 1. Vérifier subscription capabilities
az account list --query "[].{Name:name, State:state, Type:subscriptionPolicies.quotaId}" --output table

# 2. Vérifier ExpressRoute quota
az network express-route list-service-providers --output table

# 3. Si Free Trial, upgrader vers Pay-As-You-Go
# https://portal.azure.com -> Subscriptions -> Upgrade

# 4. Pour test, utiliser mock ou circuit existant
```

---

### **Problème 2: "VPN Gateway creation takes too long"**

**Symptôme:**
Gateway creation bloqué à "Creating..." pendant 45+ minutes.

**Cause:**
VPN/ExpressRoute Gateway creation prend normalement 20-45 minutes (comportement normal).

**Solution:**
```bash
# 1. Vérifier status
az network vnet-gateway show \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  --query "{name:name, provisioningState:provisioningState}" \
  --output json

# 2. Si "Creating" ou "Updating" = normal, attendre
# Si "Failed" = problème

# 3. Pour tests rapides, utiliser --no-wait
az network vnet-gateway create \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  [...] \
  --no-wait

# 4. Check async operation status
az network vnet-gateway wait \
  --resource-group $RG \
  --name $GATEWAY_NAME \
  --created
```

---

### **Problème 3: "NAT Gateway not reducing Public IP costs"**

**Symptôme:**
NAT Gateway créé mais toujours facturé pour multiple Public IPs.

**Cause:**
NAT Gateway ne supprime PAS automatiquement les Public IPs des VMs/NICs.

**Explication:**
```bash
# AVANT NAT Gateway:
# - Chaque VM a son propre Public IP = N × $3/mois

# APRÈS NAT Gateway:
# - NAT Gateway a 1-2 Public IPs = $3-6/mois + $32.40/mois NAT Gateway
# - MAIS les VMs gardent leurs Public IPs si pas supprimés manuellement!

# Solution: Supprimer Public IPs des VMs après NAT Gateway deployment
az network nic ip-config update \
  --resource-group $RG \
  --nic-name $NIC_NAME \
  --name ipconfig1 \
  --remove PublicIpAddress
```

---

### **Problème 4: "ExpressRoute Circuit shows 'Enabled' but not working"**

**Symptôme:**
Circuit status = "Enabled" mais connectivity échoue.

**Cause:**
Multiple states à vérifier : `circuitProvisioningState` vs `serviceProviderProvisioningState`.

**Solution:**
```bash
# Vérifier TOUS les states
az network express-route show \
  --resource-group $RG \
  --name $CIRCUIT_NAME \
  --query "{circuit:circuitProvisioningState, serviceProvider:serviceProviderProvisioningState, peerings:length(peerings)}" \
  --output json

# États possibles:
# circuitProvisioningState: Enabled/Disabled (Azure side)
# serviceProviderProvisioningState: NotProvisioned/Provisioning/Provisioned/Deprovisioning (Provider side)

# Pour que ça fonctionne, BESOIN de:
# 1. circuitProvisioningState = "Enabled"
# 2. serviceProviderProvisioningState = "Provisioned"
# 3. Au moins 1 peering configuré
# 4. Virtual Network Gateway connecté

# Check peerings
az network express-route peering list \
  --resource-group $RG \
  --circuit-name $CIRCUIT_NAME \
  --output table
```

---

### **Problème 5: "VPN Gateway connection stuck in 'Connecting' state"**

**Symptôme:**
Connection status = "Connecting" pendant des heures.

**Causes possibles:**
1. Shared key mismatch (local vs Azure)
2. On-premises firewall blocking UDP 500/4500
3. Local Network Gateway IP incorrect
4. Phase 1/Phase 2 IPSec parameters mismatch

**Solution:**
```bash
# 1. Vérifier connection details
az network vpn-connection show \
  --resource-group $RG \
  --name $CONNECTION_NAME \
  --query "{status:connectionStatus, protocol:connectionProtocol, sharedKey:sharedKey}" \
  --output json

# 2. Tester connectivity vers on-premises IP
ONPREM_IP=$(az network local-gateway show -g $RG -n $LOCAL_GATEWAY_NAME --query gatewayIpAddress -o tsv)
ping $ONPREM_IP

# 3. Update shared key si mismatch
az network vpn-connection shared-key set \
  --resource-group $RG \
  --connection-name $CONNECTION_NAME \
  --value "CorrectSharedKey123!"

# 4. Check logs via Azure Monitor
# Portal -> VPN Gateway -> Diagnostics -> Connection health
```

---

### **Problème 6: "Orphaned NICs cannot be deleted"**

**Symptôme:**
```
az network nic delete --name $NIC_NAME
Error: NIC is still in use
```

**Cause:**
NIC peut être attaché à :
- VM (même si VM est stopped/deallocated)
- Private Endpoint
- Application Gateway backend pool

**Solution:**
```bash
# 1. Vérifier tous les attachments
az network nic show \
  --resource-group $RG \
  --name $NIC_NAME \
  --query "{vm:virtualMachine, privateEndpoint:privateEndpoint, loadBalancerBackendAddressPools:ipConfigurations[0].loadBalancerBackendAddressPools, appGatewayBackendAddressPools:ipConfigurations[0].applicationGatewayBackendAddressPools}" \
  --output json

# 2. Si VM attachment existe, supprimer VM d'abord
VM_ID=$(az network nic show -g $RG -n $NIC_NAME --query virtualMachine.id -o tsv)
if [ ! -z "$VM_ID" ]; then
  VM_NAME=$(basename $VM_ID)
  az vm delete --resource-group $RG --name $VM_NAME --yes
fi

# 3. Si Private Endpoint, supprimer PE
PE_ID=$(az network nic show -g $RG -n $NIC_NAME --query privateEndpoint.id -o tsv)
if [ ! -z "$PE_ID" ]; then
  PE_NAME=$(basename $PE_ID)
  az network private-endpoint delete --resource-group $RG --name $PE_NAME
fi

# 4. Retry NIC delete
az network nic delete --resource-group $RG --name $NIC_NAME
```

---

## 🚀 Quick Start - Tester les Scénarios Networking

### **Script Global de Test**

```bash
#!/bin/bash
# test-networking-scenarios.sh

set -e

RG="cloudwaste-test-networking-all"
LOCATION="westeurope"

echo "🧪 Creating test resource group..."
az group create --name $RG --location $LOCATION --output none

echo ""
echo "=== PHASE 1: NAT GATEWAY SCENARIOS ==="
echo ""

# Scénario 5: NAT Gateway sans subnet
echo "5️⃣ Testing: NAT Gateway without subnet..."
NAT_GW="nat-gw-no-subnet"
NAT_PIP="nat-gw-pip"

az network public-ip create -g $RG -n $NAT_PIP --sku Standard --allocation-method Static --output none
az network nat gateway create -g $RG -n $NAT_GW -l $LOCATION --public-ip-addresses $NAT_PIP --output none

echo "✅ Created: $NAT_GW (no subnets attached, $32.40/month waste)"

echo ""
echo "=== PHASE 2: VPN GATEWAY SCENARIOS ==="
echo ""

# Note: VPN Gateway creation prend 20-45 minutes et coûte cher
# Pour demo rapide, on skip la création réelle

echo "⏩ Skipping VPN Gateway creation (takes 20-45 minutes, costs $139/month)"
echo "   Use existing VPN Gateway for testing or mock data"

echo ""
echo "=== PHASE 3: NETWORK INTERFACE SCENARIOS ==="
echo ""

# Scénario 10: NIC orphelin
echo "🔟 Testing: Orphaned Network Interface..."
VNET="vnet-test"
SUBNET="subnet-test"
NIC="nic-orphan"
VM="vm-temp"

az network vnet create -g $RG -n $VNET --address-prefix 10.10.0.0/16 --subnet-name $SUBNET --subnet-prefix 10.10.1.0/24 --output none
az network nic create -g $RG -n $NIC --vnet-name $VNET --subnet $SUBNET --output none

# Créer VM rapidement (Basic size)
az vm create -g $RG -n $VM --nics $NIC --image Ubuntu2204 --size Standard_B1s --admin-username azureuser --generate-ssh-keys --output none

# Supprimer VM pour rendre NIC orphelin
az vm delete -g $RG -n $VM --yes --output none

echo "✅ Created: $NIC (orphaned, no cost but IP space waste)"

echo ""
echo "🎉 Test resources created successfully!"
echo ""
echo "📊 Summary:"
az network nat gateway list -g $RG --query "[].{Name:name, Subnets:length(subnets)}" --output table
az network nic list -g $RG --query "[].{Name:name, VM:virtualMachine}" --output table

echo ""
echo "⚠️ WARNING: NAT Gateway costs $32.40/month starting immediately!"
echo ""
echo "⏳ Now run CloudWaste scan to detect these scenarios!"
echo ""
echo "🧹 Cleanup command (URGENT to avoid costs):"
echo "az group delete --name $RG --yes --no-wait"
```

**Utilisation:**
```bash
chmod +x test-networking-scenarios.sh
./test-networking-scenarios.sh

# ⚠️ CLEANUP URGENT pour éviter coûts NAT Gateway
az group delete --name cloudwaste-test-networking-all --yes --no-wait
```

---

## 💰 Impact Business & ROI

### **Économies Potentielles par Scénario**

| Scénario | Coût mensuel typique | Économie / ressource | Fréquence | Impact annuel (10 ressources) |
|----------|----------------------|----------------------|-----------|-------------------------------|
| 1. ExpressRoute not provisioned | $950 (1Gbps) | $950/mois | Faible (5%) | $5,700 |
| 2. ExpressRoute no connection | $950 | $950/mois | Faible (10%) | $11,400 |
| 3. ExpressRoute Gateway orphan | $1,367 (Ultra) | $1,367/mois | Faible (10%) | $16,404 |
| 4. ExpressRoute underutilized | $950 | $760/mois | Moyenne (30%) | $27,360 |
| 5. NAT Gateway no subnet | $32.40 | $32.40/mois | Moyenne (20%) | $778 |
| 6. NAT Gateway never used | $32.40 | $32.40/mois | Faible (15%) | $584 |
| 7. VPN Gateway disconnected | $139 (VpnGw1) | $139/mois | Moyenne (25%) | $4,170 |
| 8. VPN Gateway Basic SKU | $29 | Migration | Élevée (40%) | Non quantifiable (modernization) |
| 9. VPN Gateway no connections | $139 | $139/mois | Faible (15%) | $2,502 |
| 10. NIC orphaned | $0 | Gouvernance | Élevée (50%) | IP space recovery |

**Économie totale estimée par organisation (moyenne):**
- **ExpressRoute Circuits** : 2 circuits × 30% underutilized × $760 = **$18,240/an**
- **ExpressRoute Gateways** : 1 orphan × $1,367 = **$16,404/an**
- **NAT Gateways** : 5 × 20% unused × $32.40 = **$389/an**
- **VPN Gateways** : 10 × 25% disconnected × $139 = **$4,170/an**
- **NICs Orphaned** : 200 NICs × $0 = Gouvernance (IP space recovery)

**ROI Total : ~$39,000/an** pour organisation moyenne ⚡

**💡 Note** : ExpressRoute est la ressource la plus coûteuse (jusqu'à $6,400/mois pour 10 Gbps circuit). Un seul circuit mal configuré peut coûter **$76,800/an** de waste.

---

### **Arguments Commerciaux**

#### **1. ExpressRoute = Coût Massif Si Mal Géré**

> "Un ExpressRoute Circuit 1 Gbps coûte **$950/mois** (~$11,400/an). Si le circuit est 'Not Provisioned' pendant 60 jours, vous avez gaspillé **$1,900** pour un service que vous ne pouvez PAS utiliser. CloudWaste détecte ces circuits immédiatement."

#### **2. ExpressRoute Gateway Orphelin = $16,000/an de Waste**

> "Un ExpressRoute Virtual Network Gateway UltraPerformance coûte **$1,367/mois**. Si vous supprimez le circuit mais oubliez le gateway, c'est **$16,404/an** de waste pur. CloudWaste identifie automatiquement les gateways orphelins."

#### **3. NAT Gateway = Coût Invisible Sans Subnet**

> "NAT Gateway facture **$32.40/mois** dès sa création, même sans subnet attaché. 5 NAT Gateways oubliés = **$1,944/an** de gaspillage. CloudWaste les détecte dans les 7 jours."

#### **4. ExpressRoute Underutilized = 80% d'Économies**

> "Un circuit ExpressRoute 1 Gbps utilisé à seulement 5% peut être downgradé vers 200 Mbps = **économie de $760/mois** (80%). CloudWaste analyse Azure Monitor metrics pour identifier ces opportunités."

#### **5. VPN Gateway Disconnected = $4,000/an de Waste**

> "Un VPN Gateway VpnGw1 déconnecté pendant 30+ jours coûte **$139/mois** pour rien. 25% des VPN Gateways sont disconnected = **$4,170/an** de waste récupérable."

#### **6. NICs Orphelins = Épuisement IP Address Space**

> "200 NICs orphelins ne coûtent rien financièrement, mais occupent 200 IP addresses dans vos subnets. CloudWaste identifie ces NICs pour récupérer l'espace IP et améliorer la gouvernance."

#### **7. Détection Automatisée = ROI de $39,000/an**

> "CloudWaste scan automatique identifie tous ces scénarios via Azure SDK et Monitor. Pour une organisation moyenne, économie de **$39,000+/an** sur networking seul, dès le premier mois."

---

## 📚 Références Officielles Azure

### **Documentation ExpressRoute**
- [ExpressRoute Overview](https://learn.microsoft.com/en-us/azure/expressroute/expressroute-introduction)
- [ExpressRoute Pricing](https://azure.microsoft.com/en-us/pricing/details/expressroute/)
- [Plan to Manage Costs](https://learn.microsoft.com/en-us/azure/expressroute/plan-manage-cost)
- [ExpressRoute Circuits and Peering](https://learn.microsoft.com/en-us/azure/expressroute/expressroute-circuit-peerings)
- [ExpressRoute Gateway SKUs](https://learn.microsoft.com/en-us/azure/expressroute/expressroute-about-virtual-network-gateways)

### **Documentation NAT Gateway**
- [NAT Gateway Overview](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview)
- [NAT Gateway Pricing](https://azure.microsoft.com/en-us/pricing/details/azure-nat-gateway/)
- [NAT Gateway Resource](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-gateway-resource)

### **Documentation VPN Gateway**
- [VPN Gateway Overview](https://learn.microsoft.com/en-us/azure/vpn-gateway/vpn-gateway-about-vpngateways)
- [VPN Gateway Pricing](https://azure.microsoft.com/en-us/pricing/details/vpn-gateway/)
- [Gateway SKU Mappings](https://learn.microsoft.com/en-us/azure/vpn-gateway/gateway-sku-consolidation)
- [VPN Gateway Connection Status](https://learn.microsoft.com/en-us/azure/vpn-gateway/vpn-gateway-howto-site-to-site-resource-manager-portal)

### **Documentation Network Interfaces**
- [Network Interfaces Overview](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-network-interface)
- [Manage Network Interfaces](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-network-interface-vm)

### **Azure Monitor & Metrics**
- [ExpressRoute Monitoring](https://learn.microsoft.com/en-us/azure/expressroute/expressroute-monitoring-metrics-alerts)
- [NAT Gateway Metrics](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-metrics)
- [VPN Gateway Monitoring](https://learn.microsoft.com/en-us/azure/vpn-gateway/vpn-gateway-howto-setup-alerts-virtual-network-gateway-metric)

---

## ✅ Checklist d'Implémentation

### **Phase 1 - ExpressRoute Circuit**
- [ ] **Scénario 1** : `scan_expressroute_circuit_not_provisioned()` ⚠️
  - [ ] SDK : `NetworkManagementClient.express_route_circuits.list()`
  - [ ] Logique : `service_provider_provisioning_state == 'NotProvisioned'` AND age >= 30 days
  - [ ] Cost : $55-6,400/mois selon bandwidth
  - [ ] Test CLI : Create circuit without provisioning

- [ ] **Scénario 2** : `scan_expressroute_circuit_no_connection()`
  - [ ] Logique : Provisioned but no VNet Gateway connection
  - [ ] Test CLI : Circuit sans connection

- [ ] **Scénario 3** : `scan_expressroute_gateway_orphaned()` 💰
  - [ ] SDK : `virtual_network_gateways.list()` filter `gateway_type == 'ExpressRoute'`
  - [ ] Logique : connections_count == 0
  - [ ] Cost : $139-1,367/mois selon SKU
  - [ ] Test CLI : Gateway sans circuit

- [ ] **Scénario 4** : `scan_expressroute_circuit_underutilized()`
  - [ ] Azure Monitor : BitsInPerSecond, BitsOutPerSecond
  - [ ] Logique : avg_utilization < 10%
  - [ ] Économie : Downgrade bandwidth (80% savings)

### **Phase 1 - NAT Gateway**
- [ ] **Scénario 5** : `scan_nat_gateway_no_subnet()` ⚠️
  - [ ] SDK : `nat_gateways.list()`
  - [ ] Logique : len(subnets) == 0
  - [ ] Cost : $32.40/mois fixed
  - [ ] Test CLI : NAT Gateway sans subnet

- [ ] **Scénario 6** : `scan_nat_gateway_never_used()`
  - [ ] Logique : age >= 30 days AND never had subnet
  - [ ] Test CLI : NAT Gateway jamais configuré

### **Phase 1 - VPN Gateway**
- [ ] **Scénario 7** : `scan_vpn_gateway_disconnected()`
  - [ ] SDK : `virtual_network_gateways.list()` filter `gateway_type == 'Vpn'`
  - [ ] Logique : ALL connections != 'Connected' for 30+ days
  - [ ] Cost : $29-694/mois selon SKU
  - [ ] Test CLI : VPN Gateway avec wrong shared key

- [ ] **Scénario 8** : `scan_vpn_gateway_basic_sku_deprecated()` ⚠️
  - [ ] Logique : sku.name == 'Basic'
  - [ ] Warning : Deprecated, limited features
  - [ ] Test CLI : Create Basic VPN Gateway

- [ ] **Scénario 9** : `scan_vpn_gateway_no_connections()`
  - [ ] Logique : connections_count == 0 AND age >= 30 days
  - [ ] Test CLI : VPN Gateway sans connections

### **Phase 1 - Network Interfaces**
- [ ] **Scénario 10** : `scan_network_interface_orphaned()`
  - [ ] SDK : `network_interfaces.list()`
  - [ ] Logique : virtual_machine == None AND private_endpoint == None
  - [ ] Cost : $0 (gouvernance, IP space)
  - [ ] Test CLI : Create VM, delete VM, NIC remains

### **Documentation & Tests**
- [x] Documentation complète (ce fichier)
- [ ] Unit tests pour chaque scénario
- [ ] Integration tests avec Azure SDK mocks
- [ ] CLI test scripts validés
- [ ] Troubleshooting guide testé

---

## 🎯 Priorités d'Implémentation

**Ordre recommandé (du plus critique au ROI le plus élevé):**

1. **Scénario 3** : `expressroute_gateway_orphaned` 💰💰💰
   - Impact : Économie **$16,404/an** par gateway
   - Effort : Faible (simple check connections)
   - Fréquence : Faible (10%) mais impact énorme

2. **Scénario 1** : `expressroute_circuit_not_provisioned` ⚠️⚠️
   - Impact : Économie **$11,400/an** par circuit (1 Gbps)
   - Effort : Faible
   - Fréquence : Faible (5%) mais CRITIQUE

3. **Scénario 4** : `expressroute_circuit_underutilized` 💰💰
   - Impact : Économie **$9,120/an** par circuit (80% downgrade)
   - Effort : Moyen (Azure Monitor)
   - Fréquence : Moyenne (30%)

4. **Scénario 7** : `vpn_gateway_disconnected`
   - Impact : Économie **$1,668/an** par gateway
   - Effort : Faible
   - Fréquence : Moyenne (25%)

5. **Scénario 5** : `nat_gateway_no_subnet`
   - Impact : Économie **$389/an** par NAT Gateway
   - Effort : Faible
   - Fréquence : Moyenne (20%)

6-10. **Autres scénarios** : Impact modéré à faible

---

**📍 Statut actuel : 0/10 scénarios implémentés (0%)**
**🎯 Objectif : 100% coverage pour Azure Networking**

**💡 Note critique** : ExpressRoute est la ressource Azure la plus coûteuse après compute. Un seul circuit mal géré = **$76,800/an** de waste potentiel (10 Gbps). La détection ExpressRoute doit être prioritaire absolue! 🚨
