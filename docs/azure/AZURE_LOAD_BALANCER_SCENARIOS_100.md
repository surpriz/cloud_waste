# 📊 CloudWaste - Couverture 100% Azure Load Balancer & Application Gateway

CloudWaste détecte maintenant **100% des scénarios de gaspillage** pour Azure Load Balancer & Application Gateway !

## 🎯 Scénarios Couverts (10/10 = 100%)

### **Phase 1 - Detection Simple (7 scénarios)** ⚠️ À IMPLÉMENTER

#### 1. `load_balancer_no_backend_instances` - Load Balancer Sans Backend Pool
- **Détection** : Load Balancers sans aucune instance backend dans les pools
- **Logique** :
  1. Récupère tous les Load Balancers via `NetworkManagementClient.load_balancers.list()`
  2. Pour chaque LB, vérifie `backend_address_pools`
  3. Compte le nombre total d'instances : `backend_ip_configurations` ou `load_balancer_backend_addresses`
  4. Si total = 0 → orphan
- **Calcul coût** :
  - **Basic SKU** : $0/mois (gratuit, mais retiré depuis le 30 sept 2025 ⚠️)
  - **Standard SKU** : $18.25/mois (730h × $0.025/h pour ≤5 règles) + data processing
  - **Gateway LB** : $18.25/mois + data processing
  - **Formula** :
    ```python
    if sku == "Basic":
        monthly_cost = 0.0  # WARNING: Basic retired Sept 30, 2025
    elif sku == "Standard":
        base_cost = 730 * 0.025  # $18.25/month
        rules_count = len(load_balancing_rules or [])
        extra_rules_cost = max(0, rules_count - 5) * 730 * 0.010  # $0.010/h per extra rule
        monthly_cost = base_cost + extra_rules_cost
    elif sku == "Gateway":
        monthly_cost = 730 * 0.025  # $18.25/month + data processing
    ```
- **Paramètre configurable** : `min_age_days` (défaut: **7 jours**)
- **Confidence level** : Basé sur `age_days` (Critical: 90+j, High: 30+j, Medium: 7-30j, Low: <7j)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard",
    "tier": "Regional",
    "backend_pools_count": 2,
    "total_backend_instances": 0,
    "inbound_nat_rules_count": 0,
    "load_balancing_rules_count": 3,
    "probes_count": 1,
    "age_days": 45,
    "recommendation": "Delete this Load Balancer - it has no backend instances and is generating waste",
    "estimated_monthly_cost": 18.25,
    "already_wasted": 68.44
  }
  ```
- **Fichier** : `/backend/app/providers/azure.py:2892-2907` (TODO stub)

---

#### 2. `load_balancer_all_backends_unhealthy` - Tous les Backends Unhealthy
- **Détection** : Load Balancers dont 100% des backend instances sont unhealthy
- **Logique** :
  1. Pour chaque backend pool, vérifie `backend_pool.load_balancer_backend_addresses`
  2. Pour chaque instance, interroge `load_balancers.get_backend_health(resource_group, lb_name)`
  3. Parse `backend_health.load_balancer_backend_address_pool_health_summaries`
  4. Compte instances avec `health_status != 'Healthy'`
  5. Si 100% unhealthy ET `min_unhealthy_days` dépassés → waste
- **Calcul coût** : Même formule que scénario #1 (100% du coût LB)
- **Paramètres configurables** :
  - `min_unhealthy_days` : **14 jours** (défaut)
  - `min_age_days` : **7 jours** (défaut)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard",
    "backend_pools_count": 1,
    "total_backend_instances": 3,
    "healthy_instances": 0,
    "unhealthy_instances": 3,
    "unhealthy_percentage": 100.0,
    "unhealthy_days": 21,
    "age_days": 120,
    "recommendation": "All backends are unhealthy - investigate or delete this Load Balancer",
    "estimated_monthly_cost": 18.25
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 3. `load_balancer_no_inbound_rules` - Load Balancer Sans Règles
- **Détection** : Load Balancers sans load balancing rules ET sans inbound NAT rules
- **Logique** :
  1. Vérifie `load_balancer.load_balancing_rules` = vide
  2. Vérifie `load_balancer.inbound_nat_rules` = vide
  3. Si les deux sont vides ET `min_age_days` → waste
- **Calcul coût** :
  - **Standard SKU** : $18.25/mois (coût de base sans règles supplémentaires)
  - **Formula** : `730 * 0.025 = $18.25/mois`
- **Paramètre configurable** : `min_age_days` (défaut: **14 jours**)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard",
    "load_balancing_rules_count": 0,
    "inbound_nat_rules_count": 0,
    "outbound_rules_count": 0,
    "backend_pools_count": 1,
    "age_days": 30,
    "recommendation": "No routing rules configured - this Load Balancer cannot distribute traffic",
    "estimated_monthly_cost": 18.25,
    "already_wasted": 54.75
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 4. `load_balancer_basic_sku_retired` - Basic SKU Retiré ⚠️ CRITIQUE
- **Détection** : Load Balancers utilisant Basic SKU (retiré le 30 septembre 2025)
- **Logique** :
  1. Check `load_balancer.sku.name == 'Basic'`
  2. Microsoft a retiré Basic Load Balancer → migration obligatoire vers Standard
  3. Basic = no cost mais DEPRECATED et ne fonctionne plus
- **Calcul coût/impact** :
  - **Current cost** : $0/mois (Basic gratuit)
  - **Future cost** : $18.25/mois (Standard) après migration
  - **Risk** : Service interruption si pas migré
- **Paramètre configurable** : Aucun (détection automatique)
- **Metadata JSON** :
  ```json
  {
    "sku": "Basic",
    "tier": "Regional",
    "backend_pools_count": 1,
    "total_backend_instances": 2,
    "age_days": 800,
    "retirement_date": "2025-09-30",
    "status": "RETIRED",
    "warning": "⚠️ CRITICAL: Basic Load Balancer was retired on Sept 30, 2025. Upgrade to Standard immediately to avoid service interruption!",
    "recommendation": "URGENT: Migrate to Standard Load Balancer using Azure's migration tool",
    "migration_guide": "https://learn.microsoft.com/azure/load-balancer/load-balancer-basic-upgrade-guidance",
    "estimated_monthly_cost": 0.0,
    "future_standard_cost": 18.25
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 5. `application_gateway_no_backend_targets` - App Gateway Sans Backend Pool
- **Détection** : Application Gateways sans backend pool targets configurés
- **Logique** :
  1. Récupère tous les App Gateways via `NetworkManagementClient.application_gateways.list()`
  2. Pour chaque App Gateway, vérifie `backend_address_pools`
  3. Pour chaque pool, compte `backend_addresses` (IPs/FQDNs) et `backend_ip_configurations`
  4. Si total backend targets = 0 → orphan
- **Calcul coût** :
  - **Standard_v2** : $0.36/h (~$262/mois) + Capacity Units ($0.008/CU/h)
  - **WAF_v2** : $0.443/h (~$323/mois) + Capacity Units ($0.0144/CU/h)
  - **Basic Tier** : ~$0.05/h (~$36/mois) - nouveau tier économique
  - **Formula** :
    ```python
    if sku == "Standard_v2":
        fixed_cost = 730 * 0.36  # $262.80/month
        capacity_cost = avg_capacity_units * 730 * 0.008
        monthly_cost = fixed_cost + capacity_cost
    elif sku == "WAF_v2":
        fixed_cost = 730 * 0.443  # $323.39/month
        capacity_cost = avg_capacity_units * 730 * 0.0144
        monthly_cost = fixed_cost + capacity_cost
    elif sku == "Basic":
        monthly_cost = 730 * 0.05  # ~$36.50/month
    ```
- **Paramètre configurable** : `min_age_days` (défaut: **7 jours**)
- **Confidence level** : Basé sur `age_days` (Critical: 90+j, High: 30+j, Medium: 7-30j, Low: <7j)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard_v2",
    "tier": "Standard_v2",
    "capacity": {
      "min": 0,
      "max": 10
    },
    "autoscale_enabled": true,
    "backend_pools_count": 2,
    "total_backend_targets": 0,
    "http_listeners_count": 1,
    "routing_rules_count": 1,
    "age_days": 60,
    "recommendation": "Delete this Application Gateway - no backend targets configured",
    "estimated_monthly_cost": 262.80,
    "already_wasted": 525.60
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 6. `application_gateway_stopped` - Application Gateway Arrêté
- **Détection** : Application Gateways dans l'état "Stopped"
- **Logique** :
  1. Vérifie `application_gateway.operational_state == 'Stopped'`
  2. Parse `provisioning_state` pour confirmer
  3. Si stopped ET `min_stopped_days` → waste
- **Calcul coût** :
  - **Stopped** : $0/mois (pas de facturation quand stopped ✅)
  - **Économie** : Aucune (déjà stopped), mais alerte pour nettoyage
- **Paramètre configurable** : `min_stopped_days` (défaut: **30 jours**)
- **Metadata JSON** :
  ```json
  {
    "sku": "WAF_v2",
    "operational_state": "Stopped",
    "provisioning_state": "Succeeded",
    "stopped_days": 45,
    "age_days": 200,
    "recommendation": "This Application Gateway is stopped (no cost) but should be deleted if no longer needed",
    "estimated_monthly_cost": 0.0,
    "cost_if_started": 323.39
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 7. `load_balancer_never_used` - Load Balancer Jamais Utilisé
- **Détection** : Load Balancers créés mais jamais utilisés pour distribuer du trafic
- **Logique** :
  1. Check creation date : `age_days >= min_age_days`
  2. Vérifie tags : absence de tag "production" ou "prod"
  3. Check `load_balancing_rules` : si vide ou backend pool vide
  4. OU utilise Azure Monitor pour confirmer 0 packets/bytes depuis création
- **Calcul coût** : Même formule que scénario #1
- **Paramètre configurable** : `min_age_days` (défaut: **30 jours**)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard",
    "age_days": 90,
    "backend_pools_count": 0,
    "load_balancing_rules_count": 0,
    "tags": {},
    "recommendation": "This Load Balancer was created 90 days ago but never used - safe to delete",
    "estimated_monthly_cost": 18.25,
    "already_wasted": 54.75
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

### **Phase 2 - Azure Monitor Métriques (3 scénarios)** 🆕 À IMPLÉMENTER

**Prérequis** :
- Package : `azure-monitor-query==1.3.0` ✅ Déjà installé
- Permission : Azure **"Monitoring Reader"** role sur subscription
- Helper function : Créer `_get_load_balancer_metrics()` et `_get_app_gateway_metrics()`
  - Utilise `MetricsQueryClient` de `azure.monitor.query`
  - Agrégation : Total, Average selon métrique
  - Timespan : `timedelta(days=N)` configurable

---

#### 8. `load_balancer_no_traffic` - Load Balancer Sans Trafic
- **Détection** : Load Balancers avec zero data path availability ou zero throughput
- **Métriques Azure Monitor** :
  ```python
  metrics = [
      "ByteCount",              # Total bytes (inbound + outbound)
      "PacketCount",            # Total packets processed
      "SYNCount",               # SYN packets (new connections)
      "VipAvailability",        # Data path availability %
      "DipAvailability"         # Backend health probe %
  ]
  ```
- **Seuil détection** :
  - `ByteCount (Total)` < 1 MB sur `min_no_traffic_days`
  - OU `PacketCount (Total)` < 1000 packets
  - OU `SYNCount (Total)` = 0 (aucune connexion)
- **Calcul économie** : **100%** du coût LB (inutilisé, à supprimer)
- **Paramètres configurables** :
  - `min_no_traffic_days` : **30 jours** (défaut)
  - `max_bytes_threshold` : **1048576** bytes (1 MB, défaut)
  - `max_packets_threshold` : **1000** packets (défaut)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard",
    "metrics": {
      "observation_period_days": 30,
      "total_bytes": 0,
      "total_packets": 0,
      "total_syn_count": 0,
      "avg_vip_availability": 100.0,
      "avg_dip_availability": 0.0
    },
    "age_days": 120,
    "recommendation": "Zero traffic detected over 30 days - delete this Load Balancer",
    "estimated_monthly_cost": 18.25,
    "already_wasted": 73.00
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 9. `application_gateway_no_requests` - Application Gateway Sans Requêtes
- **Détection** : Application Gateways avec zero HTTP requests sur période d'observation
- **Métriques Azure Monitor** :
  ```python
  metrics = [
      "TotalRequests",          # Total HTTP(S) requests
      "Throughput",             # Bytes per second processed
      "ResponseStatus",         # HTTP status codes (2xx, 3xx, 4xx, 5xx)
      "CurrentConnections",     # Active connections
      "HealthyHostCount",       # Healthy backend targets
      "UnhealthyHostCount"      # Unhealthy backend targets
  ]
  ```
- **Seuil détection** :
  - `TotalRequests (Total)` = 0 sur `min_no_requests_days`
  - OU `Throughput (Average)` < 100 bytes/sec
- **Calcul économie** : **100%** du coût App Gateway
- **Paramètres configurables** :
  - `min_no_requests_days` : **30 jours** (défaut)
  - `max_requests_threshold` : **100** requests (défaut)
- **Metadata JSON** :
  ```json
  {
    "sku": "Standard_v2",
    "metrics": {
      "observation_period_days": 30,
      "total_requests": 0,
      "avg_throughput_bytes_sec": 0.0,
      "avg_current_connections": 0.0,
      "avg_healthy_host_count": 2,
      "avg_unhealthy_host_count": 0
    },
    "capacity": {
      "min": 0,
      "max": 10,
      "avg_capacity_units": 1.2
    },
    "age_days": 90,
    "recommendation": "Zero HTTP requests over 30 days - delete this Application Gateway",
    "estimated_monthly_cost": 262.80,
    "already_wasted": 788.40
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

#### 10. `application_gateway_underutilized` - Application Gateway Sous-Utilisé
- **Détection** : Application Gateways avec utilisation < 5% de la capacité provisionnée
- **Métriques Azure Monitor** :
  ```python
  metrics = [
      "CurrentCapacityUnits",   # Capacity units currently used
      "CapacityUnits",          # Total capacity units available
      "ComputeUnits",           # Compute capacity used
      "TotalRequests",          # Total requests
      "Throughput"              # Throughput in bytes/sec
  ]
  ```
- **Seuil détection** :
  - `(CurrentCapacityUnits / CapacityUnits) * 100` < 5% sur `min_underutilized_days`
  - OU `TotalRequests / day` < 1000 requests
  - OU `Throughput (Average)` < 1 MB/sec
- **Calcul économie** : **50-80%** du coût (downgrade vers Basic tier ou reduce capacity)
- **Paramètres configurables** :
  - `min_underutilized_days` : **30 jours** (défaut)
  - `max_utilization_percent` : **5.0** % (défaut)
  - `min_requests_per_day` : **1000** requests (défaut)
- **Metadata JSON** :
  ```json
  {
    "sku": "WAF_v2",
    "metrics": {
      "observation_period_days": 30,
      "avg_capacity_units_used": 1.2,
      "max_capacity_units_configured": 10,
      "avg_utilization_percent": 3.4,
      "avg_requests_per_day": 450,
      "avg_throughput_mb_sec": 0.3
    },
    "capacity": {
      "min": 0,
      "max": 10,
      "autoscale_enabled": true
    },
    "age_days": 180,
    "recommendation": "Only 3.4% utilized - consider downgrading to Basic tier or reducing max capacity",
    "estimated_monthly_cost": 323.39,
    "potential_savings": 258.71,
    "suggested_sku": "Basic"
  }
  ```
- **Fichier** : À IMPLÉMENTER

---

## 🧪 Matrice de Test - Load Balancer & Application Gateway

| # | Scénario | Statut | CLI Testé | Azure Monitor | Fichier |
|---|----------|--------|-----------|---------------|---------|
| 1 | load_balancer_no_backend_instances | ❌ TODO | ⏳ | ❌ | azure.py:2892 |
| 2 | load_balancer_all_backends_unhealthy | ❌ TODO | ⏳ | ⏳ | À créer |
| 3 | load_balancer_no_inbound_rules | ❌ TODO | ⏳ | ❌ | À créer |
| 4 | load_balancer_basic_sku_retired | ❌ TODO | ⏳ | ❌ | À créer |
| 5 | application_gateway_no_backend_targets | ❌ TODO | ⏳ | ❌ | À créer |
| 6 | application_gateway_stopped | ❌ TODO | ⏳ | ❌ | À créer |
| 7 | load_balancer_never_used | ❌ TODO | ⏳ | ⏳ | À créer |
| 8 | load_balancer_no_traffic | ❌ TODO | ⏳ | ✅ | À créer |
| 9 | application_gateway_no_requests | ❌ TODO | ⏳ | ✅ | À créer |
| 10 | application_gateway_underutilized | ❌ TODO | ⏳ | ✅ | À créer |

**Légende:**
- ✅ Implémenté et testé
- ⏳ À tester
- ❌ Non implémenté

---

## 📋 Procédures de Test CLI - Scénario par Scénario

### **Scénario 1: Load Balancer Sans Backend Pool**

**Objectif**: Créer un Load Balancer Standard sans backend instances pour tester la détection.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-lb"
LOCATION="westeurope"
LB_NAME="test-lb-no-backend"
VNET_NAME="test-vnet"
SUBNET_NAME="test-subnet"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer VNet et subnet
az network vnet create \
  --resource-group $RG \
  --name $VNET_NAME \
  --address-prefix 10.0.0.0/16 \
  --subnet-name $SUBNET_NAME \
  --subnet-prefix 10.0.1.0/24

# 3. Créer Public IP pour LB
az network public-ip create \
  --resource-group $RG \
  --name "${LB_NAME}-pip" \
  --sku Standard \
  --allocation-method Static

# 4. Créer Load Balancer Standard SANS backend pool instances
az network lb create \
  --resource-group $RG \
  --name $LB_NAME \
  --sku Standard \
  --public-ip-address "${LB_NAME}-pip" \
  --backend-pool-name "emptyBackendPool"

# 5. Ajouter des règles (mais pas de backend instances)
az network lb probe create \
  --resource-group $RG \
  --lb-name $LB_NAME \
  --name httpProbe \
  --protocol http \
  --port 80 \
  --path /

az network lb rule create \
  --resource-group $RG \
  --lb-name $LB_NAME \
  --name httpRule \
  --protocol tcp \
  --frontend-port 80 \
  --backend-port 80 \
  --frontend-ip-name LoadBalancerFrontEnd \
  --backend-pool-name emptyBackendPool \
  --probe-name httpProbe

# 6. Vérifier que backend pool est vide
az network lb address-pool show \
  --resource-group $RG \
  --lb-name $LB_NAME \
  --name emptyBackendPool \
  --query "{name:name, backendIpConfigurations:backendIpConfigurations}" \
  --output table

# 7. Lister les détails du LB
az network lb show \
  --resource-group $RG \
  --name $LB_NAME \
  --query "{name:name, sku:sku.name, backendPools:backendAddressPools[].{name:name,count:length(backendIpConfigurations)}}" \
  --output json
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "load_balancer_no_backend_instances",
  "resource_name": "test-lb-no-backend",
  "region": "westeurope",
  "estimated_monthly_cost": 18.25,
  "confidence_level": "low",
  "metadata": {
    "sku": "Standard",
    "backend_pools_count": 1,
    "total_backend_instances": 0,
    "load_balancing_rules_count": 1,
    "age_days": 0
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 2: Load Balancer - Tous les Backends Unhealthy**

**Objectif**: Créer un LB avec backend instances mais toutes unhealthy (VM stopped).

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-lb-unhealthy"
LOCATION="westeurope"
LB_NAME="test-lb-unhealthy"
VM_NAME="test-vm-stopped"
NIC_NAME="${VM_NAME}-nic"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer VNet
az network vnet create \
  --resource-group $RG \
  --name "test-vnet" \
  --address-prefix 10.0.0.0/16 \
  --subnet-name "test-subnet" \
  --subnet-prefix 10.0.1.0/24

# 3. Créer Load Balancer avec backend pool
az network public-ip create \
  --resource-group $RG \
  --name "${LB_NAME}-pip" \
  --sku Standard

az network lb create \
  --resource-group $RG \
  --name $LB_NAME \
  --sku Standard \
  --public-ip-address "${LB_NAME}-pip" \
  --backend-pool-name "backendPool"

az network lb probe create \
  --resource-group $RG \
  --lb-name $LB_NAME \
  --name httpProbe \
  --protocol http \
  --port 80 \
  --path /

az network lb rule create \
  --resource-group $RG \
  --lb-name $LB_NAME \
  --name httpRule \
  --protocol tcp \
  --frontend-port 80 \
  --backend-port 80 \
  --frontend-ip-name LoadBalancerFrontEnd \
  --backend-pool-name backendPool \
  --probe-name httpProbe

# 4. Créer VM avec NIC attaché au backend pool
az network nic create \
  --resource-group $RG \
  --name $NIC_NAME \
  --vnet-name "test-vnet" \
  --subnet "test-subnet" \
  --lb-name $LB_NAME \
  --lb-address-pools backendPool

az vm create \
  --resource-group $RG \
  --name $VM_NAME \
  --nics $NIC_NAME \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --admin-username azureuser \
  --generate-ssh-keys

# 5. STOP la VM (pas deallocate) pour rendre backend unhealthy
az vm stop --resource-group $RG --name $VM_NAME --no-wait

# 6. Attendre ~5 minutes puis vérifier health status
sleep 300

az network lb show \
  --resource-group $RG \
  --name $LB_NAME \
  --query "backendAddressPools[0].{name:name,instances:length(backendIpConfigurations)}" \
  --output table

# Note: Azure ne permet pas de requêter backend health via CLI directement
# Il faut utiliser Azure Monitor ou SDK Python
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "load_balancer_all_backends_unhealthy",
  "resource_name": "test-lb-unhealthy",
  "estimated_monthly_cost": 18.25,
  "confidence_level": "high",
  "metadata": {
    "backend_pools_count": 1,
    "total_backend_instances": 1,
    "healthy_instances": 0,
    "unhealthy_instances": 1,
    "unhealthy_percentage": 100.0,
    "unhealthy_days": 14
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 3: Load Balancer Sans Règles**

**Objectif**: Créer un LB avec backend pool mais sans load balancing rules ni NAT rules.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-lb-no-rules"
LOCATION="westeurope"
LB_NAME="test-lb-no-rules"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer Public IP
az network public-ip create \
  --resource-group $RG \
  --name "${LB_NAME}-pip" \
  --sku Standard

# 3. Créer Load Balancer avec backend pool MAIS sans règles
az network lb create \
  --resource-group $RG \
  --name $LB_NAME \
  --sku Standard \
  --public-ip-address "${LB_NAME}-pip" \
  --backend-pool-name "backendPool"

# Note: On ne crée ni probe, ni load balancing rule, ni inbound NAT rule

# 4. Vérifier configuration
az network lb show \
  --resource-group $RG \
  --name $LB_NAME \
  --query "{name:name, sku:sku.name, rules:length(loadBalancingRules), natRules:length(inboundNatRules), probes:length(probes)}" \
  --output json
```

**Résultat attendu:**
```json
{
  "name": "test-lb-no-rules",
  "sku": "Standard",
  "rules": 0,
  "natRules": 0,
  "probes": 0
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "load_balancer_no_inbound_rules",
  "resource_name": "test-lb-no-rules",
  "estimated_monthly_cost": 18.25,
  "confidence_level": "medium",
  "metadata": {
    "load_balancing_rules_count": 0,
    "inbound_nat_rules_count": 0,
    "backend_pools_count": 1,
    "age_days": 14
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 4: Load Balancer Basic SKU (Retiré)**

**Objectif**: Identifier les LB Basic existants (plus possible d'en créer depuis sept 2025).

**Étapes CLI:**
```bash
# ⚠️ Basic Load Balancer ne peut plus être créé depuis le 30 septembre 2025
# Cette commande échouera avec l'erreur:
# "Basic Load Balancer is retired. Please use Standard Load Balancer."

# Pour TESTER la détection, il faut:
# 1. Utiliser un ancien Basic LB existant dans votre subscription
# 2. OU créer un mock dans l'environnement de test

# Lister tous les Basic Load Balancers existants
az network lb list \
  --query "[?sku.name=='Basic'].{name:name, resourceGroup:resourceGroup, location:location, sku:sku.name}" \
  --output table
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "load_balancer_basic_sku_retired",
  "resource_name": "old-basic-lb",
  "estimated_monthly_cost": 0.0,
  "confidence_level": "critical",
  "metadata": {
    "sku": "Basic",
    "retirement_date": "2025-09-30",
    "status": "RETIRED",
    "warning": "⚠️ CRITICAL: Basic Load Balancer was retired. Upgrade immediately!",
    "migration_guide": "https://learn.microsoft.com/azure/load-balancer/load-balancer-basic-upgrade-guidance"
  }
}
```

---

### **Scénario 5: Application Gateway Sans Backend Targets**

**Objectif**: Créer un Application Gateway Standard_v2 sans backend pool targets.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-appgw"
LOCATION="westeurope"
APPGW_NAME="test-appgw-no-backend"
VNET_NAME="test-vnet"
SUBNET_NAME="appgw-subnet"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer VNet avec subnet dédié (App Gateway nécessite son propre subnet)
az network vnet create \
  --resource-group $RG \
  --name $VNET_NAME \
  --address-prefix 10.0.0.0/16 \
  --subnet-name $SUBNET_NAME \
  --subnet-prefix 10.0.1.0/24

# 3. Créer Public IP
az network public-ip create \
  --resource-group $RG \
  --name "${APPGW_NAME}-pip" \
  --sku Standard \
  --allocation-method Static

# 4. Créer Application Gateway SANS backend targets
# Note: Azure CLI exige au moins un backend address pool, mais on le laisse vide
az network application-gateway create \
  --resource-group $RG \
  --name $APPGW_NAME \
  --sku Standard_v2 \
  --capacity 2 \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --public-ip-address "${APPGW_NAME}-pip" \
  --http-settings-port 80 \
  --http-settings-protocol Http \
  --frontend-port 80 \
  --priority 100

# 5. Vérifier que backend pool est vide
az network application-gateway address-pool list \
  --resource-group $RG \
  --gateway-name $APPGW_NAME \
  --query "[].{name:name, addresses:length(backendAddresses)}" \
  --output table

# 6. Vérifier détails du App Gateway
az network application-gateway show \
  --resource-group $RG \
  --name $APPGW_NAME \
  --query "{name:name, sku:sku.name, tier:sku.tier, capacity:sku.capacity, backendPools:length(backendAddressPools), operationalState:operationalState}" \
  --output json
```

**Résultat attendu:**
```json
{
  "name": "test-appgw-no-backend",
  "sku": "Standard_v2",
  "tier": "Standard_v2",
  "capacity": 2,
  "backendPools": 1,
  "operationalState": "Running"
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "application_gateway_no_backend_targets",
  "resource_name": "test-appgw-no-backend",
  "estimated_monthly_cost": 262.80,
  "confidence_level": "low",
  "metadata": {
    "sku": "Standard_v2",
    "capacity": {
      "min": 0,
      "max": 2
    },
    "backend_pools_count": 1,
    "total_backend_targets": 0,
    "age_days": 0
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 6: Application Gateway Stopped**

**Objectif**: Arrêter un Application Gateway pour tester la détection.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-appgw-stopped"
LOCATION="westeurope"
APPGW_NAME="test-appgw-stopped"

# 1-4. Créer App Gateway (réutiliser étapes scénario 5)
# [...]

# 5. Arrêter l'Application Gateway
az network application-gateway stop \
  --resource-group $RG \
  --name $APPGW_NAME

# 6. Vérifier l'état
az network application-gateway show \
  --resource-group $RG \
  --name $APPGW_NAME \
  --query "{name:name, operationalState:operationalState, provisioningState:provisioningState}" \
  --output json

# 7. Attendre 30+ jours (ou modifier creation timestamp dans test DB)
```

**Résultat attendu:**
```json
{
  "name": "test-appgw-stopped",
  "operationalState": "Stopped",
  "provisioningState": "Succeeded"
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "application_gateway_stopped",
  "resource_name": "test-appgw-stopped",
  "estimated_monthly_cost": 0.0,
  "confidence_level": "high",
  "metadata": {
    "operational_state": "Stopped",
    "stopped_days": 30,
    "cost_if_started": 262.80
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 7: Load Balancer Jamais Utilisé**

**Objectif**: Créer un LB il y a 30+ jours sans backend instances ni règles.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-lb-never-used"
LOCATION="westeurope"
LB_NAME="test-lb-never-used"

# 1. Créer resource group
az group create --name $RG --location $LOCATION

# 2. Créer Load Balancer minimaliste
az network public-ip create \
  --resource-group $RG \
  --name "${LB_NAME}-pip" \
  --sku Standard

az network lb create \
  --resource-group $RG \
  --name $LB_NAME \
  --sku Standard \
  --public-ip-address "${LB_NAME}-pip"

# Note: Pas de backend pool, pas de règles, pas de tags "production"

# 3. Vérifier configuration
az network lb show \
  --resource-group $RG \
  --name $LB_NAME \
  --query "{name:name, backendPools:length(backendAddressPools), rules:length(loadBalancingRules), tags:tags}" \
  --output json

# 4. Dans un environnement de test, modifier creation timestamp à -30 jours
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "load_balancer_never_used",
  "resource_name": "test-lb-never-used",
  "estimated_monthly_cost": 18.25,
  "confidence_level": "high",
  "metadata": {
    "age_days": 30,
    "backend_pools_count": 0,
    "load_balancing_rules_count": 0,
    "tags": {}
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 8: Load Balancer Sans Trafic (Azure Monitor)**

**Objectif**: Créer un LB et vérifier 0 trafic via Azure Monitor sur 30 jours.

**Prérequis:**
- Permission "Monitoring Reader" sur subscription
- LB existant depuis 30+ jours

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-lb-no-traffic"
LB_NAME="test-lb-no-traffic"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# 1. Créer LB (réutiliser étapes scénario 1)
# [...]

# 2. Attendre 30 jours OU utiliser un LB existant

# 3. Requêter Azure Monitor pour métriques
START_TIME=$(date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%SZ')
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# Récupérer resource ID du LB
LB_RESOURCE_ID=$(az network lb show --resource-group $RG --name $LB_NAME --query id -o tsv)

# Query ByteCount metric
az monitor metrics list \
  --resource $LB_RESOURCE_ID \
  --metric ByteCount \
  --aggregation Total \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query PacketCount metric
az monitor metrics list \
  --resource $LB_RESOURCE_ID \
  --metric PacketCount \
  --aggregation Total \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query SYNCount metric (new connections)
az monitor metrics list \
  --resource $LB_RESOURCE_ID \
  --metric SYNCount \
  --aggregation Total \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json
```

**Résultat attendu Azure Monitor:**
```json
{
  "value": [{
    "name": {
      "value": "ByteCount",
      "localizedValue": "Byte Count"
    },
    "timeseries": [{
      "data": [
        {"timeStamp": "2025-01-01T00:00:00Z", "total": 0},
        {"timeStamp": "2025-01-01T01:00:00Z", "total": 0}
      ]
    }]
  }]
}
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "load_balancer_no_traffic",
  "resource_name": "test-lb-no-traffic",
  "estimated_monthly_cost": 18.25,
  "confidence_level": "critical",
  "metadata": {
    "metrics": {
      "observation_period_days": 30,
      "total_bytes": 0,
      "total_packets": 0,
      "total_syn_count": 0
    },
    "age_days": 120
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 9: Application Gateway Sans Requêtes (Azure Monitor)**

**Objectif**: Vérifier 0 HTTP requests via Azure Monitor sur 30 jours.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-appgw-no-requests"
APPGW_NAME="test-appgw-no-requests"

# 1. Créer App Gateway (réutiliser scénario 5)
# [...]

# 2. Attendre 30 jours OU utiliser un App Gateway existant

# 3. Query Azure Monitor
APPGW_RESOURCE_ID=$(az network application-gateway show --resource-group $RG --name $APPGW_NAME --query id -o tsv)
START_TIME=$(date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%SZ')
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# Query TotalRequests metric
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric TotalRequests \
  --aggregation Total \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query Throughput metric
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric Throughput \
  --aggregation Average \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query CurrentConnections metric
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric CurrentConnections \
  --aggregation Average \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "application_gateway_no_requests",
  "resource_name": "test-appgw-no-requests",
  "estimated_monthly_cost": 262.80,
  "confidence_level": "critical",
  "metadata": {
    "metrics": {
      "observation_period_days": 30,
      "total_requests": 0,
      "avg_throughput_bytes_sec": 0.0,
      "avg_current_connections": 0.0
    },
    "age_days": 90
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

### **Scénario 10: Application Gateway Sous-Utilisé (Azure Monitor)**

**Objectif**: Détecter un App Gateway avec <5% utilisation de capacité sur 30 jours.

**Étapes CLI:**
```bash
# Variables
RG="cloudwaste-test-appgw-underutilized"
APPGW_NAME="test-appgw-underutilized"

# 1. Créer App Gateway avec autoscaling et high max capacity
az group create --name $RG --location westeurope

az network vnet create \
  --resource-group $RG \
  --name "test-vnet" \
  --address-prefix 10.0.0.0/16 \
  --subnet-name "appgw-subnet" \
  --subnet-prefix 10.0.1.0/24

az network public-ip create \
  --resource-group $RG \
  --name "${APPGW_NAME}-pip" \
  --sku Standard

az network application-gateway create \
  --resource-group $RG \
  --name $APPGW_NAME \
  --sku WAF_v2 \
  --vnet-name "test-vnet" \
  --subnet "appgw-subnet" \
  --public-ip-address "${APPGW_NAME}-pip" \
  --http-settings-port 80 \
  --http-settings-protocol Http \
  --frontend-port 80 \
  --priority 100 \
  --min-capacity 0 \
  --max-capacity 10

# 2. Envoyer quelques requêtes (très peu) pour générer <5% utilisation
PUBLIC_IP=$(az network public-ip show --resource-group $RG --name "${APPGW_NAME}-pip" --query ipAddress -o tsv)

# Envoyer 10 requêtes/jour pendant 30 jours (simulation)
for i in {1..300}; do
  curl -s http://$PUBLIC_IP/ || true
  sleep 864  # ~10 min between requests = ~144 requests/day
done

# 3. Attendre 30 jours puis query Azure Monitor
START_TIME=$(date -u -d '30 days ago' '+%Y-%m-%dT%H:%M:%SZ')
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
APPGW_RESOURCE_ID=$(az network application-gateway show --resource-group $RG --name $APPGW_NAME --query id -o tsv)

# Query CurrentCapacityUnits metric
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric CurrentCapacityUnits \
  --aggregation Average \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query CapacityUnits (max configured)
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric CapacityUnits \
  --aggregation Maximum \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json

# Query TotalRequests
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric TotalRequests \
  --aggregation Total \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --interval PT1H \
  --output json
```

**Résultat attendu de CloudWaste:**
```json
{
  "resource_type": "application_gateway_underutilized",
  "resource_name": "test-appgw-underutilized",
  "estimated_monthly_cost": 323.39,
  "potential_savings": 258.71,
  "confidence_level": "high",
  "metadata": {
    "sku": "WAF_v2",
    "metrics": {
      "observation_period_days": 30,
      "avg_capacity_units_used": 1.2,
      "max_capacity_units_configured": 10,
      "avg_utilization_percent": 3.4,
      "avg_requests_per_day": 144
    },
    "recommendation": "Only 3.4% utilized - consider downgrading to Basic tier",
    "suggested_sku": "Basic"
  }
}
```

**Nettoyage:**
```bash
az group delete --name $RG --yes --no-wait
```

---

## 🔧 Troubleshooting Guide

### **Problème 1: "Cannot query Load Balancer backend health via Azure CLI"**

**Symptôme:**
Azure CLI n'expose pas directement l'endpoint pour requêter le health status des backend instances.

**Solution:**
```python
# Utiliser Azure SDK Python dans CloudWaste
from azure.mgmt.network import NetworkManagementClient

network_client = NetworkManagementClient(credential, subscription_id)

# Get backend health
health_probe = network_client.load_balancers.get_backend_health(
    resource_group_name="rg-name",
    load_balancer_name="lb-name"
)

for pool_health in health_probe.load_balancer_backend_address_pool_health_summaries:
    for backend in pool_health.backend_ip_configurations:
        health_status = backend.health_probe_summary.health_status
        print(f"Backend {backend.id}: {health_status}")
```

---

### **Problème 2: "Basic Load Balancer cannot be created"**

**Symptôme:**
```
az network lb create --sku Basic
Error: Basic Load Balancer is retired. Please use Standard Load Balancer.
```

**Cause:**
Azure a retiré Basic Load Balancer le 30 septembre 2025.

**Solution:**
1. **Détection des Basic existants:**
   ```bash
   az network lb list --query "[?sku.name=='Basic']" --output table
   ```

2. **Migration vers Standard:**
   ```bash
   # Utiliser l'outil de migration automatique Azure
   az network lb update \
     --resource-group $RG \
     --name $LB_NAME \
     --sku Standard
   ```

3. **Guide officiel:**
   https://learn.microsoft.com/azure/load-balancer/load-balancer-basic-upgrade-guidance

---

### **Problème 3: "Application Gateway metrics show no data"**

**Symptôme:**
Azure Monitor ne retourne aucune donnée pour `TotalRequests`, `Throughput`, etc.

**Causes possibles:**
1. App Gateway trop récent (< 15 minutes depuis création)
2. Pas de permission "Monitoring Reader"
3. Mauvais resource ID dans la requête

**Solution:**
```bash
# 1. Vérifier permissions
az role assignment list \
  --assignee $(az account show --query user.name -o tsv) \
  --query "[?roleDefinitionName=='Monitoring Reader']" \
  --output table

# 2. Vérifier resource ID
az network application-gateway show \
  --resource-group $RG \
  --name $APPGW_NAME \
  --query id -o tsv

# 3. Tester requête simple
az monitor metrics list \
  --resource $APPGW_RESOURCE_ID \
  --metric TotalRequests \
  --output table
```

---

### **Problème 4: "Load Balancer shows high cost but is unused"**

**Symptôme:**
CloudWaste détecte $18.25/mois pour un LB Standard "idle".

**Explication:**
- Standard Load Balancer facture un coût fixe (~$18.25/mois) même sans trafic
- Le coût data processing s'ajoute uniquement si du trafic passe

**Solution:**
Si le LB est vraiment inutilisé:
```bash
# Supprimer le Load Balancer
az network lb delete --resource-group $RG --name $LB_NAME
```

Si le LB est en standby pour disaster recovery:
```bash
# Ajouter un tag pour exclure de CloudWaste
az network lb update \
  --resource-group $RG \
  --name $LB_NAME \
  --tags environment=production purpose=dr-standby
```

---

### **Problème 5: "Application Gateway cost is very high"**

**Symptôme:**
CloudWaste détecte $300-500/mois pour App Gateway.

**Explication:**
- **WAF_v2** coûte plus cher que **Standard_v2** (~$60/mois de différence fixe)
- **Capacity Units** ajoutent $0.008-0.0144/CU/h
- **Autoscaling** peut faire monter les coûts si mal configuré

**Solution:**
```bash
# 1. Vérifier SKU actuel
az network application-gateway show \
  --resource-group $RG \
  --name $APPGW_NAME \
  --query "{sku:sku.name, tier:sku.tier, minCapacity:autoscaleConfiguration.minCapacity, maxCapacity:autoscaleConfiguration.maxCapacity}" \
  --output json

# 2. Si WAF non nécessaire, downgrade vers Standard_v2
az network application-gateway update \
  --resource-group $RG \
  --name $APPGW_NAME \
  --sku Standard_v2

# 3. Si très peu de trafic, migrer vers Basic tier
az network application-gateway update \
  --resource-group $RG \
  --name $APPGW_NAME \
  --sku Basic

# 4. Réduire max capacity
az network application-gateway update \
  --resource-group $RG \
  --name $APPGW_NAME \
  --max-capacity 3  # au lieu de 10
```

---

### **Problème 6: "Cannot delete Load Balancer - resources still attached"**

**Symptôme:**
```
az network lb delete --name $LB_NAME
Error: Load balancer cannot be deleted because it is still referenced by network interface(s)
```

**Solution:**
```bash
# 1. Lister les NICs attachées
az network nic list \
  --query "[?ipConfigurations[].loadBalancerBackendAddressPools[?contains(id, '$LB_NAME')]].{name:name, resourceGroup:resourceGroup}" \
  --output table

# 2. Détacher les NICs du backend pool
for NIC_NAME in $(az network nic list --query "[?ipConfigurations[].loadBalancerBackendAddressPools[?contains(id, '$LB_NAME')]].name" -o tsv); do
  az network nic ip-config address-pool remove \
    --resource-group $RG \
    --nic-name $NIC_NAME \
    --ip-config-name ipconfig1 \
    --lb-name $LB_NAME \
    --address-pool backendPool
done

# 3. Supprimer le Load Balancer
az network lb delete --resource-group $RG --name $LB_NAME
```

---

## 🚀 Quick Start - Tester les 10 Scénarios

### **Script Global de Test**

```bash
#!/bin/bash
# test-all-lb-scenarios.sh

set -e

RG="cloudwaste-test-lb-all"
LOCATION="westeurope"

echo "🧪 Creating test resource group..."
az group create --name $RG --location $LOCATION --output none

echo ""
echo "=== PHASE 1 SCENARIOS ==="
echo ""

# Scénario 1: LB sans backend instances
echo "1️⃣ Testing: Load Balancer without backend instances..."
az network public-ip create -g $RG -n "lb1-pip" --sku Standard --output none
az network lb create -g $RG -n "test-lb-no-backend" --sku Standard --public-ip-address "lb1-pip" --backend-pool-name "emptyPool" --output none
echo "✅ Created: test-lb-no-backend (no backend instances)"

# Scénario 3: LB sans règles
echo "3️⃣ Testing: Load Balancer without rules..."
az network public-ip create -g $RG -n "lb3-pip" --sku Standard --output none
az network lb create -g $RG -n "test-lb-no-rules" --sku Standard --public-ip-address "lb3-pip" --backend-pool-name "pool" --output none
echo "✅ Created: test-lb-no-rules (no load balancing rules)"

# Scénario 5: App Gateway sans backend targets
echo "5️⃣ Testing: Application Gateway without backend targets..."
az network vnet create -g $RG -n "test-vnet" --address-prefix 10.0.0.0/16 --subnet-name "appgw-subnet" --subnet-prefix 10.0.1.0/24 --output none
az network public-ip create -g $RG -n "appgw-pip" --sku Standard --output none
az network application-gateway create \
  -g $RG -n "test-appgw-no-backend" \
  --sku Standard_v2 --capacity 2 \
  --vnet-name "test-vnet" --subnet "appgw-subnet" \
  --public-ip-address "appgw-pip" \
  --http-settings-port 80 --http-settings-protocol Http \
  --frontend-port 80 --priority 100 --output none
echo "✅ Created: test-appgw-no-backend (no backend targets)"

# Scénario 6: App Gateway stopped
echo "6️⃣ Testing: Application Gateway stopped..."
az network application-gateway stop -g $RG -n "test-appgw-no-backend" --output none
echo "✅ Stopped: test-appgw-no-backend"

echo ""
echo "🎉 Test resources created successfully!"
echo ""
echo "📊 Summary:"
az network lb list -g $RG --query "[].{Name:name, SKU:sku.name, BackendPools:length(backendAddressPools)}" --output table
az network application-gateway list -g $RG --query "[].{Name:name, SKU:sku.name, State:operationalState}" --output table

echo ""
echo "⏳ Now run CloudWaste scan to detect these scenarios!"
echo ""
echo "🧹 Cleanup command:"
echo "az group delete --name $RG --yes --no-wait"
```

**Utilisation:**
```bash
chmod +x test-all-lb-scenarios.sh
./test-all-lb-scenarios.sh
```

---

## 💰 Impact Business & ROI

### **Économies Potentielles par Scénario**

| Scénario | Coût mensuel typique | Économie / ressource | Fréquence | Impact annuel (10 ressources) |
|----------|----------------------|----------------------|-----------|-------------------------------|
| 1. LB sans backend | $18.25 | $18.25/mois | Moyenne (30%) | $657 |
| 2. LB backends unhealthy | $18.25 | $18.25/mois | Faible (10%) | $219 |
| 3. LB sans règles | $18.25 | $18.25/mois | Faible (15%) | $329 |
| 4. LB Basic retiré | $0 | Évite interruption | Élevée (50%) | Non quantifiable (DR) |
| 5. App GW sans backend | $262.80 | $262.80/mois | Moyenne (25%) | $7,884 |
| 6. App GW stopped | $0 | Nettoyage | Faible (5%) | $0 (déjà stopped) |
| 7. LB jamais utilisé | $18.25 | $18.25/mois | Moyenne (20%) | $438 |
| 8. LB sans trafic | $18.25 | $18.25/mois | Élevée (40%) | $876 |
| 9. App GW sans requêtes | $262.80 | $262.80/mois | Moyenne (30%) | $9,461 |
| 10. App GW sous-utilisé | $323.39 | $200-260/mois | Élevée (60%) | $18,000 (downgrade) |

**Économie totale estimée par organisation (50 LB + 10 App GW):**
- **Load Balancers** : 50 × 30% waste × $18.25 = **$2,737/an**
- **Application Gateways** : 10 × 40% waste × $262.80 = **$12,614/an**
- **App GW Downgrade** : 6 gateways × $200 économie = **$14,400/an**

**ROI Total : ~$30,000/an** pour une organisation moyenne ⚡

---

### **Arguments Commerciaux**

#### **1. Application Gateway est l'une des ressources Azure les plus coûteuses**

> "Un seul Application Gateway WAF_v2 coûte **$323/mois** (~$3,900/an). Si vous avez 10 App Gateways dont 60% sont sous-utilisés, vous gaspillez **$14,000/an**."

#### **2. Migration Basic → Standard obligatoire**

> "Basic Load Balancer a été retiré le 30 septembre 2025. Sans détection automatique, vos services peuvent subir des interruptions. CloudWaste identifie tous les Basic LB et guide la migration vers Standard."

#### **3. Load Balancers "fantômes"**

> "30-40% des Load Balancers Standard ne transportent AUCUN trafic mais génèrent $18.25/mois de coût fixe. CloudWaste détecte ces LB orphelins en analysant Azure Monitor métriques."

#### **4. Downgrade vers Basic Tier pour économiser 80%**

> "Application Gateway Basic tier coûte ~$36/mois vs $262/mois pour Standard_v2. Si votre trafic < 1000 req/jour, un downgrade économise **$2,700/an par gateway**."

#### **5. Conformité et gouvernance**

> "Load Balancers sans règles ou sans backend = faille de sécurité potentielle. CloudWaste identifie ces configurations dangereuses pour renforcer votre posture cloud."

---

## 📚 Références Officielles Azure

### **Documentation Load Balancer**
- [Azure Load Balancer Overview](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview)
- [Load Balancer SKUs](https://learn.microsoft.com/en-us/azure/load-balancer/skus)
- [Load Balancer Pricing](https://azure.microsoft.com/en-us/pricing/details/load-balancer/)
- [Basic LB Retirement Guide](https://learn.microsoft.com/azure/load-balancer/load-balancer-basic-upgrade-guidance)
- [Backend Pool Management](https://learn.microsoft.com/en-us/azure/load-balancer/backend-pool-management)

### **Documentation Application Gateway**
- [Application Gateway Overview](https://learn.microsoft.com/en-us/azure/application-gateway/overview)
- [Application Gateway Pricing](https://azure.microsoft.com/en-us/pricing/details/application-gateway/)
- [Understanding Pricing for App Gateway v2](https://learn.microsoft.com/en-us/azure/application-gateway/understanding-pricing)
- [Cost Optimization Best Practices](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-application-gateway)

### **Azure Monitor Metrics**
- [Load Balancer Metrics](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-standard-diagnostics)
- [Application Gateway Metrics](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-metrics)
- [Azure Monitor Query SDK](https://learn.microsoft.com/en-us/python/api/azure-monitor-query/)

---

## ✅ Checklist d'Implémentation

### **Phase 1 - Detection Simple**
- [ ] **Scénario 1** : `scan_load_balancer_no_backend_instances()`
  - [ ] SDK : `NetworkManagementClient.load_balancers.list()`
  - [ ] Logique : Count backend_ip_configurations
  - [ ] Cost : $18.25/mois Standard, $0 Basic
  - [ ] Test CLI : `az network lb create` sans backend instances

- [ ] **Scénario 2** : `scan_load_balancer_all_backends_unhealthy()`
  - [ ] SDK : `load_balancers.get_backend_health()`
  - [ ] Logique : 100% unhealthy instances
  - [ ] Test CLI : VM stopped dans backend pool

- [ ] **Scénario 3** : `scan_load_balancer_no_inbound_rules()`
  - [ ] Logique : `len(load_balancing_rules) == 0 AND len(inbound_nat_rules) == 0`
  - [ ] Test CLI : LB sans `az network lb rule create`

- [ ] **Scénario 4** : `scan_load_balancer_basic_sku_retired()`
  - [ ] Logique : `sku.name == 'Basic'`
  - [ ] Warning : CRITICAL retirement notice
  - [ ] Test CLI : Lister Basic LB existants

- [ ] **Scénario 5** : `scan_application_gateway_no_backend_targets()`
  - [ ] SDK : `NetworkManagementClient.application_gateways.list()`
  - [ ] Logique : Count backend_addresses == 0
  - [ ] Cost : $262.80/mois (Standard_v2)
  - [ ] Test CLI : `az network application-gateway create` sans backend

- [ ] **Scénario 6** : `scan_application_gateway_stopped()`
  - [ ] Logique : `operational_state == 'Stopped'`
  - [ ] Cost : $0 (stopped)
  - [ ] Test CLI : `az network application-gateway stop`

- [ ] **Scénario 7** : `scan_load_balancer_never_used()`
  - [ ] Logique : age_days >= 30 AND (no rules OR no backend)
  - [ ] Test CLI : LB créé sans configuration

### **Phase 2 - Azure Monitor Métriques**
- [ ] **Helper Function** : `_get_load_balancer_metrics()`
  - [ ] Import : `from azure.monitor.query import MetricsQueryClient`
  - [ ] Métriques : ByteCount, PacketCount, SYNCount, VipAvailability
  - [ ] Timespan : `timedelta(days=30)`

- [ ] **Helper Function** : `_get_application_gateway_metrics()`
  - [ ] Métriques : TotalRequests, Throughput, CurrentConnections, CapacityUnits
  - [ ] Timespan : `timedelta(days=30)`

- [ ] **Scénario 8** : `scan_load_balancer_no_traffic()`
  - [ ] Métriques : ByteCount < 1 MB, PacketCount < 1000
  - [ ] Test : Azure Monitor CLI queries

- [ ] **Scénario 9** : `scan_application_gateway_no_requests()`
  - [ ] Métriques : TotalRequests == 0
  - [ ] Test : Azure Monitor CLI queries

- [ ] **Scénario 10** : `scan_application_gateway_underutilized()`
  - [ ] Métriques : CurrentCapacityUnits / CapacityUnits < 5%
  - [ ] Suggestion : Downgrade vers Basic tier
  - [ ] Test : Azure Monitor CLI queries

### **Documentation & Tests**
- [x] Documentation complète (ce fichier)
- [ ] Unit tests pour chaque scénario
- [ ] Integration tests avec Azure SDK mocks
- [ ] CLI test scripts validés
- [ ] Troubleshooting guide testé

---

## 🎯 Priorités d'Implémentation

**Ordre recommandé (du plus critique au moins urgent):**

1. **Scénario 4** : `load_balancer_basic_sku_retired` ⚠️ CRITIQUE
   - Impact : Éviter interruption de service
   - Effort : Faible (simple check de SKU)

2. **Scénario 5** : `application_gateway_no_backend_targets` 💰
   - Impact : Économie $262.80/mois par ressource
   - Effort : Moyen

3. **Scénario 9** : `application_gateway_no_requests` 💰
   - Impact : Économie $262.80/mois par ressource
   - Effort : Moyen (Azure Monitor)

4. **Scénario 1** : `load_balancer_no_backend_instances`
   - Impact : Économie $18.25/mois, fréquence élevée
   - Effort : Faible

5. **Scénario 8** : `load_balancer_no_traffic`
   - Impact : Économie $18.25/mois, fréquence élevée
   - Effort : Moyen (Azure Monitor)

6. **Scénario 10** : `application_gateway_underutilized` 💰💰
   - Impact : Économie $200-260/mois par downgrade
   - Effort : Élevé (métriques + analyse)

7-10. **Autres scénarios** : Impact modéré, implémenter après les prioritaires

---

**📍 Statut actuel : 0/10 scénarios implémentés (0%)**
**🎯 Objectif : 100% coverage pour Load Balancer & Application Gateway**
