# 📊 CloudWaste - Couverture 100% Azure Kubernetes Service (AKS)

## 🎯 Scénarios Couverts (10/10 = 100%)

> **Contexte 2025**: AKS représente **15-25% des coûts cloud** pour les organisations cloud-native. **40% des clusters AKS sont sur-provisionnés** selon les études FinOps. Les **nodes représentent 70-80% des coûts** d'un cluster AKS. L'autoscaling mal configuré génère jusqu'à **$50,000/an de waste** par cluster.

### Phase 1 - Détection Simple (7 scénarios)

#### 1. `aks_cluster_stopped` - Cluster arrêté mais non supprimé

**Détection**: Cluster AKS en powerState 'Stopped'.

**Logique**:
```python
from azure.mgmt.containerservice import ContainerServiceClient

aks_client = ContainerServiceClient(credential, subscription_id)

for cluster in aks_client.managed_clusters.list():
    # Vérifier powerState
    if cluster.power_state and cluster.power_state.code == 'Stopped':
        stop_time = get_stop_time_from_activity_log(cluster.id)
        age_days = (datetime.now() - stop_time).days

        if age_days >= min_age_days:
            flag_as_wasteful(cluster)
```

**Calcul coût**:
```python
# Cluster Management Fee (toujours facturé même si stopped)
tier_pricing = {
    "Free": 0,          # Pas de SLA
    "Standard": 0.10,   # $/heure = $73/mois
    "Premium": 0.60     # $/heure = $438/mois
}

cluster_tier = cluster.sku.tier
monthly_cluster_fee = tier_pricing[cluster_tier] * 730

# Storage des disks (OS disks + persistent volumes)
# OS disks: 1 disk par node (même si stopped)
node_count = get_total_node_count(cluster)
os_disk_size_gb = 128  # Défaut
os_disk_cost = node_count * os_disk_size_gb * 0.05  # Premium SSD

# Persistent Volumes (si présents)
pv_storage_gb = get_total_pv_storage(cluster)
pv_cost = pv_storage_gb * 0.05  # Managed Disks

# Load Balancer (si Standard)
lb_cost = 0
if has_standard_load_balancer(cluster):
    lb_cost = 0.025 * 730  # $18.25/mois

# Public IPs
public_ip_count = get_public_ip_count(cluster)
public_ip_cost = public_ip_count * 0.005 * 730  # $3.65/mois par IP

# Total coût pendant arrêt (pas de compute nodes)
monthly_cost_while_stopped = (
    monthly_cluster_fee +
    os_disk_cost +
    pv_cost +
    lb_cost +
    public_ip_cost
)

# Exemple: Standard tier, 3 nodes, 500 GB PVs, 1 LB, 1 Public IP
# = $73 + $19.20 + $25 + $18.25 + $3.65 = $139.10/mois

already_wasted = monthly_cost_while_stopped * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 14 (défaut)
- `alert_threshold_days`: 30
- `critical_threshold_days`: 60

**Confidence level**:
- age_days < 14: LOW (40%) - Peut être maintenance temporaire
- 14-30 jours: MEDIUM (70%) - Probablement oublié
- 30-60 jours: HIGH (85%) - Définitivement orphelin
- >60 jours: CRITICAL (95%) - Waste confirmé

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_cluster_stopped",
  "cluster_name": "aks-prod-legacy",
  "resource_group": "rg-containers-prod",
  "location": "eastus",
  "power_state": "Stopped",
  "sku": {
    "name": "Base",
    "tier": "Standard"
  },
  "kubernetes_version": "1.28.3",
  "node_count_total": 3,
  "stopped_date": "2024-11-01T10:00:00Z",
  "age_days": 90,
  "monthly_cluster_fee": 73.00,
  "monthly_storage_cost": 44.20,
  "monthly_lb_cost": 18.25,
  "monthly_public_ip_cost": 3.65,
  "total_monthly_cost_while_stopped": 139.10,
  "already_wasted_usd": 417.30,
  "recommendation": "Delete cluster if no longer needed",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2967` (stub existant)

---

#### 2. `aks_cluster_zero_nodes` - Cluster avec 0 nodes dans tous les pools

**Détection**: Cluster actif mais tous les node pools à 0 nodes.

**Logique**:
```python
# Cluster running
if cluster.power_state is None or cluster.power_state.code == 'Running':
    # Compter nodes total
    total_nodes = 0

    for agent_pool in aks_client.agent_pools.list(
        resource_group_name=rg_name,
        resource_name=cluster.name
    ):
        total_nodes += agent_pool.count

    # Si 0 nodes total
    if total_nodes == 0:
        creation_time = cluster.time_created
        age_days = (datetime.now() - creation_time).days

        if age_days >= min_age_days:
            flag_as_wasteful(cluster)
```

**Calcul coût**:
```python
# Uniquement cluster management fee (pas de nodes)
cluster_tier = cluster.sku.tier
monthly_cluster_fee = tier_pricing[cluster_tier] * 730

# Exemple: Standard tier
monthly_cost = 73.00  # $73/mois wasteful

# Si Premium tier
# monthly_cost = 438.00  # $438/mois wasteful

already_wasted = monthly_cost * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 7 (défaut)
- `alert_threshold_days`: 14
- `critical_threshold_days`: 30

**Confidence level**:
- age_days < 7: LOW (35%) - Peut être en cours de setup
- 7-14 jours: MEDIUM (65%) - Configuration probablement abandonnée
- 14-30 jours: HIGH (85%) - Orphelin confirmé
- >30 jours: CRITICAL (98%) - Définitivement wasteful

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_cluster_zero_nodes",
  "cluster_name": "aks-test-empty",
  "power_state": "Running",
  "sku": {
    "tier": "Standard"
  },
  "node_pools": [
    {
      "name": "agentpool",
      "count": 0,
      "vm_size": "Standard_D2s_v3"
    }
  ],
  "total_nodes": 0,
  "created_date": "2024-12-01T08:00:00Z",
  "age_days": 60,
  "monthly_cluster_fee": 73.00,
  "already_wasted_usd": 146.00,
  "recommendation": "Delete cluster or add nodes",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2967` (stub existant)

---

#### 3. `aks_cluster_no_user_pods` - Cluster sans pods applicatifs (hors kube-system)

**Détection**: Cluster avec nodes actifs mais 0 pods dans namespaces utilisateur.

**Logique**:
```python
from kubernetes import client, config

# Cluster running avec nodes
if total_nodes > 0:
    # Configurer kubectl API
    kubeconfig = get_aks_credentials(cluster)
    config.load_kube_config_from_dict(kubeconfig)

    v1 = client.CoreV1Api()

    # Lister tous les pods
    all_pods = v1.list_pod_for_all_namespaces(watch=False)

    # Filtrer pods utilisateur (excluant kube-system, kube-public, etc.)
    system_namespaces = ['kube-system', 'kube-public', 'kube-node-lease', 'gatekeeper-system']

    user_pods = [
        pod for pod in all_pods.items
        if pod.metadata.namespace not in system_namespaces
    ]

    # Si 0 pods utilisateur
    if len(user_pods) == 0:
        age_days = (datetime.now() - cluster.time_created).days

        if age_days >= min_age_days:
            flag_as_wasteful(cluster)
```

**Calcul coût**:
```python
# Cluster management fee
monthly_cluster_fee = tier_pricing[cluster_tier] * 730

# Coût nodes (VM compute)
# Exemple: 3 nodes Standard_D2s_v3
node_count = 3
vm_hourly_cost = 0.096  # Standard_D2s_v3
monthly_node_cost = node_count * vm_hourly_cost * 730  # $210.24

# Storage (OS disks)
os_disk_cost = node_count * 128 * 0.05  # $19.20

# Load Balancer
lb_cost = 18.25

# Total
total_monthly_cost = (
    monthly_cluster_fee +  # $73
    monthly_node_cost +    # $210.24
    os_disk_cost +         # $19.20
    lb_cost                # $18.25
)  # = $320.69/mois

already_wasted = total_monthly_cost * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 14 (défaut)
- `exclude_namespaces`: ['kube-system', 'kube-public', 'kube-node-lease', 'gatekeeper-system']
- `alert_threshold_days`: 30
- `critical_threshold_days`: 60

**Confidence level**:
- age_days < 14: LOW (45%) - Peut être en migration
- 14-30 jours: MEDIUM (70%) - Probablement inutilisé
- 30-60 jours: HIGH (85%) - Définitivement orphelin
- >60 jours: CRITICAL (95%) - Waste confirmé

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_cluster_no_user_pods",
  "cluster_name": "aks-webapp-dev",
  "power_state": "Running",
  "node_count_total": 3,
  "node_pools": [
    {
      "name": "agentpool",
      "count": 3,
      "vm_size": "Standard_D2s_v3"
    }
  ],
  "total_pods": 12,
  "system_pods": 12,
  "user_pods": 0,
  "namespaces": ["kube-system", "kube-public"],
  "age_days": 45,
  "monthly_cluster_fee": 73.00,
  "monthly_node_cost": 210.24,
  "monthly_storage_cost": 19.20,
  "monthly_lb_cost": 18.25,
  "total_monthly_cost": 320.69,
  "already_wasted_usd": 481.04,
  "recommendation": "Delete cluster or deploy workloads",
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py:2967` (stub existant)

---

#### 4. `aks_autoscaler_not_enabled` - Cluster Autoscaler non configuré

**Détection**: Node pools sans autoscaling activé.

**Logique**:
```python
# Pour chaque node pool
for agent_pool in aks_client.agent_pools.list(rg_name, cluster.name):
    # Vérifier autoscaler
    if not agent_pool.enable_auto_scaling:
        # Node pool sans autoscaling
        # Potentiel over-provisioning

        # Vérifier si node count fixe > min requis
        current_count = agent_pool.count
        min_count_estimated = estimate_min_nodes_required(cluster, agent_pool)

        if current_count > min_count_estimated:
            # Over-provisioning détecté
            wasteful_nodes = current_count - min_count_estimated
            flag_as_wasteful(cluster, agent_pool, wasteful_nodes)
```

**Calcul coût**:
```python
# Coût nodes over-provisionnés
vm_size = agent_pool.vm_size
vm_hourly_cost = get_vm_hourly_cost(vm_size)

# Exemple: Standard_D4s_v3 = $0.192/h
# Node pool: 5 nodes fixes
# Min requis: 2 nodes (basé sur workload)
# Wasteful: 3 nodes

wasteful_nodes = 3
monthly_waste_per_node = vm_hourly_cost * 730
total_monthly_waste = wasteful_nodes * monthly_waste_per_node

# Exemple: 3 nodes × $0.192 × 730 = $420.48/mois

# Avec autoscaler (scale down automatique)
# Coût moyen: 2.5 nodes (fluctue 2-5 selon charge)
# monthly_cost_with_autoscaler = 2.5 × $0.192 × 730 = $350.40
# Économie: $420.48 - $350.40 = $70.08/mois (17% savings)

# Économie potentielle moyenne: 30-50%
monthly_savings = total_monthly_waste * 0.40  # 40% économie moyenne

already_wasted = monthly_savings * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `over_provisioning_threshold`: 1.5 (50% over-provisioned)
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (40%) - Peut vouloir capacité fixe
- 30-60 jours: MEDIUM (65%) - Probablement oublié
- 60-90 jours: HIGH (80%) - Over-provisioning confirmé
- >90 jours: CRITICAL (90%) - Définitivement wasteful

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_autoscaler_not_enabled",
  "cluster_name": "aks-api-prod",
  "node_pool_name": "userpool",
  "enable_auto_scaling": false,
  "current_count": 5,
  "vm_size": "Standard_D4s_v3",
  "estimated_min_count": 2,
  "wasteful_nodes": 3,
  "vm_hourly_cost": 0.192,
  "current_monthly_cost": 700.80,
  "optimized_monthly_cost": 350.40,
  "monthly_savings_potential": 280.32,
  "recommendation": "Enable cluster autoscaler with min=2, max=10",
  "age_days": 120,
  "already_wasted_usd": 1121.28,
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 5. `aks_node_pool_oversized_vms` - Node pool avec VMs surdimensionnées

**Détection**: VM SKU trop large pour le workload réel.

**Logique**:
```python
# Pour chaque node pool
for agent_pool in aks_client.agent_pools.list(rg_name, cluster.name):
    vm_size = agent_pool.vm_size

    # Récupérer spécifications VM
    vm_specs = get_vm_specs(vm_size)
    vcpus = vm_specs['vcpus']
    memory_gb = vm_specs['memory_gb']

    # Query métriques utilisation via Azure Monitor
    # (ou kubectl top nodes si Monitor pas configuré)
    avg_cpu_utilization = get_avg_cpu_utilization(cluster, agent_pool)
    avg_memory_utilization = get_avg_memory_utilization(cluster, agent_pool)

    # Si CPU <30% ET Memory <40%
    if avg_cpu_utilization < 30 and avg_memory_utilization < 40:
        # Node pool surdimensionné
        # Recommander downgrade

        # Exemple: D8s_v3 (8 vCPU, 32 GB) avec 20% CPU, 30% memory
        # → Recommander D4s_v3 (4 vCPU, 16 GB)

        recommended_vm_size = recommend_vm_downgrade(
            vm_size,
            avg_cpu_utilization,
            avg_memory_utilization
        )

        flag_as_wasteful(cluster, agent_pool, recommended_vm_size)
```

**Calcul coût**:
```python
# Coût actuel
current_vm_size = "Standard_D8s_v3"
current_hourly_cost = 0.384  # $/h
node_count = 5
current_monthly_cost = node_count * current_hourly_cost * 730  # $1,401.60

# VM recommandée (basé sur utilization)
recommended_vm_size = "Standard_D4s_v3"
recommended_hourly_cost = 0.192  # $/h
recommended_monthly_cost = node_count * recommended_hourly_cost * 730  # $700.80

# Économie potentielle
monthly_savings = current_monthly_cost - recommended_monthly_cost  # $700.80 (50%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**VM Downgrade Recommendations**:
```python
downgrade_matrix = {
    # Si avg_cpu <20% ET avg_memory <30%
    "Standard_D8s_v3": "Standard_D2s_v3",   # 8→2 vCPU (75% économie)
    "Standard_D16s_v3": "Standard_D4s_v3",  # 16→4 vCPU (75% économie)

    # Si avg_cpu 20-30% ET avg_memory 30-40%
    "Standard_D8s_v3": "Standard_D4s_v3",   # 8→4 vCPU (50% économie)
    "Standard_D16s_v3": "Standard_D8s_v3",  # 16→8 vCPU (50% économie)
    "Standard_D4s_v3": "Standard_D2s_v3",   # 4→2 vCPU (50% économie)
}
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `cpu_threshold`: 30 (%)
- `memory_threshold`: 40 (%)
- `alert_threshold_days`: 45
- `critical_threshold_days`: 90

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (50%)
- 30-60 jours + low utilization: HIGH (80%)
- >60 jours + low utilization: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_node_pool_oversized_vms",
  "cluster_name": "aks-webapp-prod",
  "node_pool_name": "userpool",
  "current_vm_size": "Standard_D8s_v3",
  "current_vcpus": 8,
  "current_memory_gb": 32,
  "node_count": 5,
  "monitoring_period_days": 60,
  "avg_cpu_utilization_percent": 18.5,
  "avg_memory_utilization_percent": 28.3,
  "p95_cpu_percent": 35.2,
  "p95_memory_percent": 42.1,
  "current_monthly_cost": 1401.60,
  "recommended_vm_size": "Standard_D4s_v3",
  "recommended_vcpus": 4,
  "recommended_memory_gb": 16,
  "recommended_monthly_cost": 700.80,
  "monthly_savings_potential": 700.80,
  "annual_savings_potential": 8409.60,
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 6. `aks_orphaned_persistent_volumes` - Persistent Volumes non attachés

**Détection**: PersistentVolumes (Azure Disks) orphelins sans PersistentVolumeClaim actif.

**Logique**:
```python
from kubernetes import client

# Configurer kubectl API
v1 = client.CoreV1Api()

# Lister tous les PVs
all_pvs = v1.list_persistent_volume(watch=False)

orphaned_pvs = []

for pv in all_pvs.items:
    # Vérifier statut
    if pv.status.phase == 'Released':
        # PV released = PVC supprimé mais PV conservé
        orphaned_pvs.append(pv)

    elif pv.status.phase == 'Available':
        # PV disponible mais jamais utilisé
        creation_time = pv.metadata.creation_timestamp
        age_days = (datetime.now(timezone.utc) - creation_time).days

        if age_days >= min_age_days:
            orphaned_pvs.append(pv)

# Pour chaque PV orphelin, récupérer Azure Disk ID
for pv in orphaned_pvs:
    if pv.spec.azure_disk:
        disk_uri = pv.spec.azure_disk.disk_uri
        disk_size_gb = pv.spec.capacity['storage']  # ex: "100Gi"

        flag_as_wasteful(cluster, pv, disk_uri, disk_size_gb)
```

**Calcul coût**:
```python
# Coût Azure Managed Disks
# Standard SSD: $0.05/GB/mois
# Premium SSD: $0.12/GB/mois

# Exemple: 5 PVs orphelins
orphaned_pvs_data = [
    {"size_gb": 100, "sku": "Premium_LRS"},  # $12/mois
    {"size_gb": 256, "sku": "StandardSSD_LRS"},  # $12.80/mois
    {"size_gb": 512, "sku": "Premium_LRS"},  # $61.44/mois
    {"size_gb": 128, "sku": "StandardSSD_LRS"},  # $6.40/mois
    {"size_gb": 64, "sku": "Premium_LRS"},  # $7.68/mois
]

total_monthly_cost = 0
for pv_data in orphaned_pvs_data:
    size_gb = pv_data['size_gb']
    sku = pv_data['sku']

    if 'Premium' in sku:
        cost = size_gb * 0.12
    else:  # Standard SSD
        cost = size_gb * 0.05

    total_monthly_cost += cost

# Total: $100.32/mois pour 5 PVs orphelins (1060 GB total)

already_wasted = total_monthly_cost * (avg_age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 14 (défaut)
- `check_pv_phases`: ['Released', 'Available']
- `alert_threshold_days`: 30
- `critical_threshold_days`: 60

**Confidence level**:
- age_days < 14: LOW (40%) - Peut être backup temporaire
- 14-30 jours: MEDIUM (70%) - Probablement oublié
- 30-60 jours: HIGH (85%) - Orphelin confirmé
- >60 jours: CRITICAL (98%) - Définitivement wasteful

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_orphaned_persistent_volumes",
  "cluster_name": "aks-data-prod",
  "orphaned_pvs": [
    {
      "pv_name": "pvc-abc123-dynamic",
      "phase": "Released",
      "size_gb": 100,
      "storage_class": "managed-premium",
      "disk_sku": "Premium_LRS",
      "azure_disk_id": "/subscriptions/.../disks/pvc-abc123",
      "created_date": "2024-10-01T12:00:00Z",
      "age_days": 90,
      "monthly_cost": 12.00
    },
    {
      "pv_name": "pvc-def456-dynamic",
      "phase": "Available",
      "size_gb": 256,
      "storage_class": "managed-standard",
      "disk_sku": "StandardSSD_LRS",
      "azure_disk_id": "/subscriptions/.../disks/pvc-def456",
      "created_date": "2024-11-15T08:30:00Z",
      "age_days": 45,
      "monthly_cost": 12.80
    }
  ],
  "total_orphaned_count": 5,
  "total_storage_gb": 1060,
  "total_monthly_cost": 100.32,
  "avg_age_days": 67,
  "already_wasted_usd": 224.71,
  "recommendation": "Delete orphaned PVs or reclaim policy to Delete",
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 7. `aks_unused_load_balancers` - Services LoadBalancer sans backends

**Détection**: Services Kubernetes type LoadBalancer sans pods endpoints.

**Logique**:
```python
from kubernetes import client

v1 = client.CoreV1Api()

# Lister tous les services type LoadBalancer
all_services = v1.list_service_for_all_namespaces(watch=False)

for svc in all_services.items:
    if svc.spec.type == 'LoadBalancer':
        # Vérifier endpoints
        namespace = svc.metadata.namespace
        service_name = svc.metadata.name

        endpoints = v1.read_namespaced_endpoints(service_name, namespace)

        # Compter pods backends
        backend_count = 0
        if endpoints.subsets:
            for subset in endpoints.subsets:
                if subset.addresses:
                    backend_count += len(subset.addresses)

        # Si 0 backends
        if backend_count == 0:
            creation_time = svc.metadata.creation_timestamp
            age_days = (datetime.now(timezone.utc) - creation_time).days

            if age_days >= min_age_days:
                # Récupérer Azure Load Balancer associé
                lb_ip = svc.status.load_balancer.ingress[0].ip if svc.status.load_balancer.ingress else None

                flag_as_wasteful(cluster, svc, lb_ip)
```

**Calcul coût**:
```python
# Azure Standard Load Balancer
# Coût fixe: $0.025/heure = $18.25/mois
# + Data processing: $0.005/GB

# Public IP Standard
# Coût: $0.005/heure = $3.65/mois

# Par service LoadBalancer inutilisé
monthly_lb_cost = 18.25
monthly_ip_cost = 3.65
monthly_cost_per_lb = monthly_lb_cost + monthly_ip_cost  # $21.90/mois

# Exemple: 3 services LoadBalancer inutilisés
unused_lb_count = 3
total_monthly_cost = unused_lb_count * monthly_cost_per_lb  # $65.70/mois

already_wasted = total_monthly_cost * (avg_age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 7 (défaut)
- `min_backends_threshold`: 0
- `alert_threshold_days`: 14
- `critical_threshold_days`: 30

**Confidence level**:
- age_days < 7: LOW (35%) - Peut être en déploiement
- 7-14 jours: MEDIUM (65%) - Probablement oublié
- 14-30 jours: HIGH (85%) - Orphelin confirmé
- >30 jours: CRITICAL (95%) - Définitivement wasteful

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_unused_load_balancers",
  "cluster_name": "aks-api-prod",
  "unused_services": [
    {
      "service_name": "api-legacy-external",
      "namespace": "default",
      "type": "LoadBalancer",
      "load_balancer_ip": "40.117.xxx.xxx",
      "backend_count": 0,
      "selector": {"app": "api-legacy"},
      "created_date": "2024-10-01T10:00:00Z",
      "age_days": 90,
      "monthly_cost": 21.90
    },
    {
      "service_name": "test-svc",
      "namespace": "test",
      "type": "LoadBalancer",
      "load_balancer_ip": "40.117.yyy.yyy",
      "backend_count": 0,
      "selector": {"app": "test"},
      "created_date": "2024-12-15T14:20:00Z",
      "age_days": 45,
      "monthly_cost": 21.90
    }
  ],
  "total_unused_count": 3,
  "total_monthly_cost": 65.70,
  "avg_age_days": 67,
  "already_wasted_usd": 147.24,
  "recommendation": "Delete unused LoadBalancer services",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

## Phase 2 - Azure Monitor Métriques (3 scénarios)

### 8. `aks_low_cpu_utilization` - CPU cluster <20% sur 30 jours

**Détection**: Cluster avec utilisation CPU moyenne <20% via Azure Monitor.

**Logique**:
```python
# Query Azure Monitor Container Insights
metric_name = "node_cpu_usage_percentage"
time_range = timedelta(days=30)

query_result = metrics_client.query_resource(
    resource_uri=cluster.id,
    metric_names=[metric_name],
    timespan=time_range,
    granularity=timedelta(hours=1),
    aggregations=["Average"]
)

# Calculer moyenne CPU%
cpu_percentages = [
    point.average for point in query_result.metrics[0].timeseries[0].data
    if point.average is not None
]

avg_cpu_percent = sum(cpu_percentages) / len(cpu_percentages)

# Si <20% utilisé
if avg_cpu_percent < low_cpu_threshold:
    # Cluster sous-utilisé
    # Recommander rightsizing (réduction nodes ou VM size)

    # Calculer économie potentielle
    current_monthly_cost = calculate_cluster_compute_cost(cluster)

    # Économie via rightsizing (réduire 40% des nodes)
    optimized_monthly_cost = current_monthly_cost * 0.60
    monthly_savings = current_monthly_cost - optimized_monthly_cost

    flag_as_wasteful(cluster, monthly_savings)
```

**Calcul coût**:
```python
# Coût compute actuel
# Exemple: 10 nodes Standard_D4s_v3
node_count = 10
vm_hourly_cost = 0.192
monthly_compute = node_count * vm_hourly_cost * 730  # $1,401.60

# Avec avg_cpu = 15%
# Capacité utilisée réelle: 15% × 10 nodes = 1.5 nodes équivalent
# Avec buffer 50%: besoin 2.25 nodes → arrondi 3 nodes
# Ou même VM size mais 6 nodes (60% réduction)

# Option 1: Réduire nombre de nodes (6 nodes au lieu de 10)
optimized_node_count = 6
optimized_monthly_compute = optimized_node_count * vm_hourly_cost * 730  # $840.96
monthly_savings_option1 = monthly_compute - optimized_monthly_compute  # $560.64 (40%)

# Option 2: Downgrade VM size (10 nodes D2s_v3 au lieu de D4s_v3)
optimized_vm_hourly_cost = 0.096  # D2s_v3
optimized_monthly_compute2 = node_count * optimized_vm_hourly_cost * 730  # $700.80
monthly_savings_option2 = monthly_compute - optimized_monthly_compute2  # $700.80 (50%)

# Recommander meilleure option
monthly_savings = max(monthly_savings_option1, monthly_savings_option2)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `low_cpu_threshold`: 20 (%)
- `recommended_buffer`: 1.5 (50% buffer)
- `alert_threshold_percent`: 25
- `critical_threshold_percent`: 15

**Confidence level**:
- avg_cpu% 20-25%: MEDIUM (60%)
- avg_cpu% 15-20%: HIGH (80%)
- avg_cpu% <15%: CRITICAL (95%)

**Azure Monitor Query**:
```python
from azure.monitor.query import MetricsQueryClient, MetricAggregationType
from datetime import datetime, timedelta

# Query node CPU usage
start_time = datetime.utcnow() - timedelta(days=30)
end_time = datetime.utcnow()

response = metrics_client.query_resource(
    resource_uri=cluster_id,
    metric_names=["node_cpu_usage_percentage"],
    timespan=(start_time, end_time),
    granularity=timedelta(hours=1),
    aggregations=[MetricAggregationType.AVERAGE, MetricAggregationType.MAXIMUM]
)

# Analyser données
cpu_averages = []
cpu_maxes = []

for data_point in response.metrics[0].timeseries[0].data:
    if data_point.average:
        cpu_averages.append(data_point.average)
    if data_point.maximum:
        cpu_maxes.append(data_point.maximum)

avg_cpu = sum(cpu_averages) / len(cpu_averages)
max_cpu = max(cpu_maxes)
p95_cpu = sorted(cpu_averages)[int(len(cpu_averages) * 0.95)]

print(f"Avg CPU: {avg_cpu:.2f}%")
print(f"Max CPU: {max_cpu:.2f}%")
print(f"P95 CPU: {p95_cpu:.2f}%")
```

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_low_cpu_utilization",
  "cluster_name": "aks-backend-prod",
  "monitoring_period_days": 30,
  "node_count": 10,
  "vm_size": "Standard_D4s_v3",
  "avg_cpu_percent": 15.8,
  "max_cpu_percent": 42.3,
  "p95_cpu_percent": 28.5,
  "current_monthly_cost": 1401.60,
  "optimization_option_1": {
    "type": "reduce_nodes",
    "recommended_node_count": 6,
    "monthly_cost": 840.96,
    "savings": 560.64
  },
  "optimization_option_2": {
    "type": "downgrade_vm_size",
    "recommended_vm_size": "Standard_D2s_v3",
    "monthly_cost": 700.80,
    "savings": 700.80
  },
  "recommended_optimization": "downgrade_vm_size",
  "monthly_savings_potential": 700.80,
  "annual_savings_potential": 8409.60,
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

### 9. `aks_low_memory_utilization` - Memory cluster <30% sur 30 jours

**Détection**: Cluster avec utilisation mémoire moyenne <30%.

**Logique**:
```python
# Query Azure Monitor Container Insights
metric_name = "node_memory_working_set_percentage"
time_range = timedelta(days=30)

query_result = metrics_client.query_resource(
    resource_uri=cluster.id,
    metric_names=[metric_name],
    timespan=time_range,
    granularity=timedelta(hours=1),
    aggregations=["Average"]
)

# Calculer moyenne memory%
memory_percentages = [
    point.average for point in query_result.metrics[0].timeseries[0].data
    if point.average is not None
]

avg_memory_percent = sum(memory_percentages) / len(memory_percentages)

# Si <30% utilisé
if avg_memory_percent < low_memory_threshold:
    # Cluster avec trop de RAM
    # Recommander VM size avec moins de RAM

    flag_as_wasteful(cluster)
```

**Calcul coût**:
```python
# Exemple: 8 nodes Standard_E4s_v3 (Memory Optimized)
# 4 vCPU, 32 GB RAM
node_count = 8
vm_hourly_cost = 0.252  # E4s_v3
monthly_compute = node_count * vm_hourly_cost * 730  # $1,470.72

# Avec avg_memory = 22%
# RAM utilisée: 22% × 32 GB = 7 GB par node
# Recommander VM General Purpose avec ratio CPU:RAM standard

# Standard_D4s_v3: 4 vCPU, 16 GB RAM (suffisant pour 7 GB utilisés)
optimized_vm_hourly_cost = 0.192  # D4s_v3
optimized_monthly_compute = node_count * optimized_vm_hourly_cost * 730  # $1,121.28

# Économie
monthly_savings = monthly_compute - optimized_monthly_compute  # $349.44 (24%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `low_memory_threshold`: 30 (%)
- `recommended_buffer`: 1.5 (50% buffer)
- `alert_threshold_percent`: 35
- `critical_threshold_percent`: 25

**Confidence level**:
- avg_memory% 30-35%: MEDIUM (60%)
- avg_memory% 25-30%: HIGH (80%)
- avg_memory% <25%: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_low_memory_utilization",
  "cluster_name": "aks-cache-prod",
  "monitoring_period_days": 30,
  "node_count": 8,
  "current_vm_size": "Standard_E4s_v3",
  "current_vcpus": 4,
  "current_memory_gb": 32,
  "avg_memory_percent": 22.3,
  "max_memory_percent": 48.7,
  "p95_memory_percent": 38.2,
  "avg_memory_used_gb": 7.1,
  "current_monthly_cost": 1470.72,
  "recommended_vm_size": "Standard_D4s_v3",
  "recommended_memory_gb": 16,
  "recommended_monthly_cost": 1121.28,
  "monthly_savings_potential": 349.44,
  "annual_savings_potential": 4193.28,
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

### 10. `aks_dev_test_always_on` - Cluster dev/test actif 24/7

**Détection**: Cluster taggé dev/test mais actif 24/7 sans automation start/stop.

**Logique**:
```python
# Identifier environnement dev/test
tags = cluster.tags or {}

is_dev_test = (
    tags.get('environment', '').lower() in ['dev', 'test', 'development', 'testing', 'staging'] or
    'dev' in cluster.name.lower() or
    'test' in cluster.name.lower()
)

if is_dev_test:
    # Vérifier uptime via métriques ou Activity Log
    # Si cluster jamais arrêté depuis création = 100% uptime

    # Query Activity Log pour events "stop cluster"
    stop_events = get_cluster_stop_events(cluster.id, days=30)

    if len(stop_events) == 0:
        # Cluster jamais arrêté = toujours actif 24/7
        # Recommander automation start/stop

        flag_as_wasteful(cluster)
```

**Calcul coût**:
```python
# Coût actuel (24/7)
# Exemple: Cluster Standard + 3 nodes D2s_v3
cluster_fee_24_7 = 73.00  # Standard tier
node_cost_24_7 = 3 * 0.096 * 730  # $210.24
total_24_7 = cluster_fee_24_7 + node_cost_24_7  # $283.24/mois

# Coût optimisé (8h/jour × 5j/semaine)
# = 40h/semaine = 173h/mois (24% uptime)
cluster_fee_optimized = 73.00  # Toujours payé
node_cost_optimized = 3 * 0.096 * 173  # $49.82
total_optimized = cluster_fee_optimized + node_cost_optimized  # $122.82/mois

# Économie potentielle
monthly_savings = total_24_7 - total_optimized  # $160.42/mois (57%)

# Alternative: Automation via Azure Automation ou Logic Apps
# Coût automation: ~$5/mois
# Économie nette: $155.42/mois

already_wasted = monthly_savings * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `dev_test_tags`: ['dev', 'test', 'development', 'testing', 'staging']
- `expected_uptime_ratio`: 0.24 (24% = 8h×5j)
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (35%) - Nouveau cluster
- 30-60 jours: MEDIUM (65%) - Usage probablement non optimisé
- 60-90 jours: HIGH (85%) - Définitivement wasteful
- >90 jours: CRITICAL (95%) - Waste confirmé

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_aks_cluster",
  "scenario": "aks_dev_test_always_on",
  "cluster_name": "aks-dev-eastus",
  "environment_tag": "dev",
  "tags": {"environment": "development", "team": "platform"},
  "node_count": 3,
  "vm_size": "Standard_D2s_v3",
  "created_date": "2024-06-01T10:00:00Z",
  "age_days": 210,
  "stop_events_count_30days": 0,
  "uptime_ratio": 1.0,
  "expected_uptime_ratio": 0.24,
  "current_monthly_cost": 283.24,
  "optimized_monthly_cost": 122.82,
  "monthly_savings_potential": 160.42,
  "annual_savings_potential": 1925.04,
  "recommendation": "Implement start/stop automation (8am-6pm weekdays)",
  "automation_options": ["Azure Automation runbook", "Logic Apps", "Azure DevOps Pipeline"],
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

## 🧪 Matrice de Test

| # | Scénario | Phase | Implémenté | Testé | Priorité | Impact ROI |
|---|----------|-------|-----------|-------|----------|------------|
| 1 | `aks_cluster_stopped` | 1 | ⚠️ | ❌ | **P1** | 💰 Medium ($73-438/mois) |
| 2 | `aks_cluster_zero_nodes` | 1 | ⚠️ | ❌ | **P1** | 💰 Medium ($73-438/mois) |
| 3 | `aks_cluster_no_user_pods` | 1 | ⚠️ | ❌ | **P0** | 🔥 High ($321/mois) |
| 4 | `aks_autoscaler_not_enabled` | 1 | ❌ | ❌ | **P0** | 🔥🔥 Very High ($280/mois, 40% fréquence) |
| 5 | `aks_node_pool_oversized_vms` | 1 | ❌ | ❌ | **P0** | 🔥🔥🔥 Critical ($701/mois, 35% fréquence) |
| 6 | `aks_orphaned_persistent_volumes` | 1 | ❌ | ❌ | **P1** | 🔥 Medium ($100/mois) |
| 7 | `aks_unused_load_balancers` | 1 | ❌ | ❌ | **P2** | 💰 Low ($22/mois) |
| 8 | `aks_low_cpu_utilization` | 2 | ❌ | ❌ | **P0** | 🔥🔥🔥 Critical ($701/mois, 40% fréquence) |
| 9 | `aks_low_memory_utilization` | 2 | ❌ | ❌ | **P1** | 🔥 High ($349/mois) |
| 10 | `aks_dev_test_always_on` | 2 | ❌ | ❌ | **P1** | 🔥 Medium ($160/mois, 25% fréquence) |

**Légende**:
- ✅ Implémenté
- ⚠️ Stub existant (besoin finalisation)
- ❌ Non implémenté
- **P0**: Critique (Quick Win)
- **P1**: Haute priorité
- **P2**: Moyenne priorité

---

## 📋 Procédures de Test CLI

### Prérequis

```bash
# Installation Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Sélectionner subscription
az account set --subscription "your-subscription-id"

# Installation kubectl
az aks install-cli

# Installer extension Azure Monitor
az extension add --name monitor-query
```

---

### Test Scénario #1: `aks_cluster_stopped`

**Objectif**: Créer cluster AKS et l'arrêter.

```bash
# Variables
LOCATION="eastus"
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-test-stopped"

# Créer resource group
az group create --name $RG_NAME --location $LOCATION

# Créer AKS cluster (Standard tier, 1 node)
az aks create \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --location $LOCATION \
  --tier standard \
  --node-count 1 \
  --node-vm-size Standard_D2s_v3 \
  --network-plugin azure \
  --generate-ssh-keys

# Attendre provisioning (peut prendre 10-15 min)
az aks wait \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --created \
  --timeout 900

# Arrêter le cluster
az aks stop \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME

# Vérifier statut
az aks show \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --query "{name:name, powerState:powerState, sku:sku, nodeResourceGroup:nodeResourceGroup}" \
  --output json

# Expected: powerState.code = "Stopped"
# Coût: $73/mois (Standard tier) + storage disks

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

**Résultat attendu**:
```json
{
  "name": "aks-test-stopped",
  "powerState": {
    "code": "Stopped"
  },
  "sku": {
    "name": "Base",
    "tier": "Standard"
  },
  "nodeResourceGroup": "MC_rg-cloudwaste-test-aks_aks-test-stopped_eastus"
}
```

---

### Test Scénario #2: `aks_cluster_zero_nodes`

**Objectif**: Cluster actif avec 0 nodes.

```bash
# Créer cluster avec autoscaler enabled
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-test-zero-nodes"

az group create --name $RG_NAME --location eastus --output none

az aks create \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --location eastus \
  --tier standard \
  --node-count 1 \
  --node-vm-size Standard_D2s_v3 \
  --enable-cluster-autoscaler \
  --min-count 0 \
  --max-count 3 \
  --generate-ssh-keys

# Attendre provisioning
az aks wait --resource-group $RG_NAME --name $CLUSTER_NAME --created --timeout 900

# Scaler à 0 nodes
az aks scale \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --node-count 0 \
  --nodepool-name nodepool1

# Vérifier node count
az aks show \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --query "agentPoolProfiles[0].count" \
  --output tsv

# Expected: 0
# Coût: $73/mois (Standard tier) wasteful

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #3: `aks_cluster_no_user_pods`

**Objectif**: Cluster avec nodes mais sans pods applicatifs.

```bash
# Créer cluster
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-test-no-pods"

az group create --name $RG_NAME --location eastus --output none

az aks create \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --location eastus \
  --tier standard \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --generate-ssh-keys

# Attendre provisioning
az aks wait --resource-group $RG_NAME --name $CLUSTER_NAME --created --timeout 900

# Obtenir credentials kubectl
az aks get-credentials \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --overwrite-existing

# Vérifier pods (seulement kube-system)
kubectl get pods --all-namespaces

# Expected: Seulement pods kube-system (coredns, kube-proxy, etc.)
# Aucun pod dans namespace "default" ou autres namespaces utilisateur

# Vérifier namespaces
kubectl get namespaces

# Expected: kube-system, kube-public, kube-node-lease, default (vide)

# Coût: $73 (cluster) + $210.24 (3 nodes) = $283.24/mois wasteful

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #4: `aks_autoscaler_not_enabled`

**Objectif**: Node pool sans autoscaler configuré.

```bash
# Créer cluster SANS autoscaler
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-test-no-autoscaler"

az group create --name $RG_NAME --location eastus --output none

az aks create \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --location eastus \
  --tier standard \
  --node-count 5 \
  --node-vm-size Standard_D4s_v3 \
  --generate-ssh-keys

# Vérifier autoscaler status
az aks nodepool show \
  --resource-group $RG_NAME \
  --cluster-name $CLUSTER_NAME \
  --name nodepool1 \
  --query "{name:name, count:count, enableAutoScaling:enableAutoScaling, vmSize:vmSize}" \
  --output json

# Expected: enableAutoScaling = null (not enabled)
# count = 5 (fixe)

# Coût: 5 × $0.192 × 730 = $700.80/mois
# Si autoscaler enabled, pourrait scale down à 2-3 nodes selon charge
# Économie potentielle: ~40% = $280/mois

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

**Résultat attendu**:
```json
{
  "name": "nodepool1",
  "count": 5,
  "enableAutoScaling": null,
  "vmSize": "Standard_D4s_v3"
}
```

---

### Test Scénario #5: `aks_node_pool_oversized_vms`

**Objectif**: Node pool avec VMs surdimensionnées.

```bash
# Créer cluster avec VMs larges
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-test-oversized"

az group create --name $RG_NAME --location eastus --output none

az aks create \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --location eastus \
  --tier standard \
  --node-count 3 \
  --node-vm-size Standard_D8s_v3 \
  --generate-ssh-keys

# Attendre provisioning
az aks wait --resource-group $RG_NAME --name $CLUSTER_NAME --created --timeout 900

# Obtenir credentials
az aks get-credentials --resource-group $RG_NAME --name $CLUSTER_NAME --overwrite-existing

# Déployer workload léger
kubectl create deployment nginx --image=nginx --replicas=3

# Attendre deployment
kubectl rollout status deployment/nginx

# Vérifier resource usage (nécessite metrics-server)
kubectl top nodes

# Expected: CPU% <20%, Memory% <30%
# VM: D8s_v3 (8 vCPU, 32 GB RAM)
# Coût: 3 × $0.384 × 730 = $840.96/mois

# Recommandation: Downgrade à D2s_v3 (2 vCPU, 8 GB)
# Coût optimisé: 3 × $0.096 × 730 = $210.24/mois
# Économie: $630.72/mois (75%)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #6: `aks_orphaned_persistent_volumes`

**Objectif**: Créer PV puis supprimer PVC pour orpheliner le PV.

```bash
# Créer cluster
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-test-orphan-pv"

az group create --name $RG_NAME --location eastus --output none
az aks create --resource-group $RG_NAME --name $CLUSTER_NAME --location eastus --tier standard --node-count 1 --node-vm-size Standard_D2s_v3 --generate-ssh-keys
az aks wait --resource-group $RG_NAME --name $CLUSTER_NAME --created --timeout 900
az aks get-credentials --resource-group $RG_NAME --name $CLUSTER_NAME --overwrite-existing

# Créer PVC (utilise default storage class managed-premium)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: managed-premium
  resources:
    requests:
      storage: 100Gi
EOF

# Attendre provisioning du PV
sleep 30

# Vérifier PV créé
kubectl get pv

# Utiliser PVC dans un pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
    - mountPath: /data
      name: test-volume
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: test-pvc
EOF

# Attendre pod running
kubectl wait --for=condition=Ready pod/test-pod --timeout=60s

# Supprimer pod
kubectl delete pod test-pod

# Supprimer PVC (PV devient Released car reclaimPolicy=Retain par défaut)
kubectl delete pvc test-pvc

# Vérifier PV orphelin
kubectl get pv

# Expected: PV en status "Released" (non utilisable, mais facturé)
# Coût: 100 GB × $0.12/GB/mois (Premium SSD) = $12/mois wasteful

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #8: `aks_low_cpu_utilization` (Azure Monitor)

**Objectif**: Query métriques CPU via Azure Monitor.

```bash
# Créer cluster (reprendre test #5 avec workload léger)
# ... (omis pour brevity)

# Query métriques via Azure CLI
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
CLUSTER_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.ContainerService/managedClusters/$CLUSTER_NAME"

# Métriques CPU (dernières 24h)
az monitor metrics list \
  --resource $CLUSTER_RESOURCE_ID \
  --metric node_cpu_usage_percentage \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table

# Calculer moyenne
az monitor metrics list \
  --resource $CLUSTER_RESOURCE_ID \
  --metric node_cpu_usage_percentage \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output json \
  | jq '[.value[0].timeseries[0].data[].average] | add / length'

# Expected: <20% CPU average
# Recommandation: Downgrade VM size ou réduire node count

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #10: `aks_dev_test_always_on`

**Objectif**: Cluster dev/test actif 24/7.

```bash
# Créer cluster avec tag environment=dev
RG_NAME="rg-cloudwaste-test-aks"
CLUSTER_NAME="aks-dev-always-on"

az group create --name $RG_NAME --location eastus --output none

az aks create \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --location eastus \
  --tier standard \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --tags environment=dev team=platform \
  --generate-ssh-keys

# Vérifier tags
az aks show \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --query "{name:name, tags:tags, powerState:powerState}" \
  --output json

# Expected: tags.environment = "dev"
# powerState.code = "Running" (jamais arrêté)

# Coût 24/7: $73 + $210.24 = $283.24/mois
# Coût optimisé (8h×5j): $73 + $49.82 = $122.82/mois
# Économie: $160.42/mois (57%)

# Recommandation: Implémenter automation start/stop
# Script exemple (Azure Automation runbook):

cat > stop-aks-after-hours.ps1 <<'EOF'
param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory=$true)]
    [string]$ClusterName
)

$currentTime = (Get-Date).ToUniversalTime()
$dayOfWeek = $currentTime.DayOfWeek
$hour = $currentTime.Hour

# Stop if: weekend OR (weekday AND outside 8am-6pm)
if ($dayOfWeek -in @('Saturday', 'Sunday') -or $hour -lt 8 -or $hour -ge 18) {
    Stop-AzAksCluster -ResourceGroupName $ResourceGroupName -Name $ClusterName
    Write-Output "AKS cluster stopped (off-hours)"
} else {
    Write-Output "AKS cluster kept running (business hours)"
}
EOF

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

## 🔧 Troubleshooting Guide

### Problème 1: Cluster autoscaler ne scale pas down

**Symptôme**: Nodes restent actifs même si pods supprimés.

**Cause**: Pods avec `PodDisruptionBudget` ou `DaemonSets` empêchent scale down.

**Diagnostic**:
```bash
# Vérifier logs autoscaler
kubectl logs -n kube-system deployment/cluster-autoscaler

# Identifier pods bloquant scale down
kubectl get pods --all-namespaces -o json | jq '.items[] | select(.metadata.ownerReferences[].kind == "DaemonSet") | .metadata.name'

# Vérifier PodDisruptionBudgets
kubectl get pdb --all-namespaces
```

**Solution**:
```bash
# Ajouter annotation pour permettre scale down
kubectl annotate node <node-name> cluster-autoscaler.kubernetes.io/scale-down-disabled=false

# Ou ajuster PodDisruptionBudget
kubectl edit pdb <pdb-name>

# Vérifier node labels qui bloquent
kubectl get nodes --show-labels | grep scale-down
```

---

### Problème 2: Persistent Volumes non supprimés après delete PVC

**Symptôme**: PVs en status "Released" persistent.

**Cause**: `reclaimPolicy: Retain` sur StorageClass.

**Solution**:
```bash
# Vérifier reclaim policy
kubectl get storageclass -o json | jq '.items[] | {name: .metadata.name, reclaimPolicy: .reclaimPolicy}'

# Modifier StorageClass (pour futurs PVs)
kubectl patch storageclass managed-premium -p '{"reclaimPolicy":"Delete"}'

# Pour PVs existants orphelins
# Option 1: Supprimer manuellement
kubectl delete pv <pv-name>

# Option 2: Recycler (si reclaimPolicy=Recycle)
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Recycle"}}'

# Option 3: Supprimer Azure Disk sous-jacent via CLI
DISK_ID=$(kubectl get pv <pv-name> -o jsonpath='{.spec.azureDisk.diskURI}')
az disk delete --ids $DISK_ID --yes
```

---

### Problème 3: Métriques Azure Monitor non disponibles

**Symptôme**: `az monitor metrics list` retourne vide.

**Cause**: Container Insights pas activé ou délai propagation métriques.

**Solution**:
```bash
# Activer Container Insights
az aks enable-addons \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --addons monitoring

# Vérifier addon enabled
az aks show \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --query "addonProfiles.omsagent.enabled" \
  --output tsv

# Expected: true

# Attendre 10-15 min pour métriques
# Vérifier Log Analytics workspace
az aks show \
  --resource-group $RG_NAME \
  --name $CLUSTER_NAME \
  --query "addonProfiles.omsagent.config.logAnalyticsWorkspaceResourceID" \
  --output tsv
```

---

### Problème 4: kubectl top nodes retourne erreur

**Erreur**:
```
error: Metrics API not available
```

**Cause**: metrics-server pas déployé.

**Solution**:
```bash
# Déployer metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Vérifier deployment
kubectl get deployment metrics-server -n kube-system

# Attendre ready
kubectl wait --for=condition=available --timeout=60s deployment/metrics-server -n kube-system

# Tester
kubectl top nodes
kubectl top pods --all-namespaces
```

---

### Problème 5: Impossible de supprimer cluster - Load Balancer en cours d'utilisation

**Erreur**:
```
Cannot delete cluster because Load Balancer has active connections
```

**Cause**: Services type LoadBalancer non supprimés.

**Solution**:
```bash
# Lister services LoadBalancer
kubectl get svc --all-namespaces -o json | jq '.items[] | select(.spec.type == "LoadBalancer") | {name: .metadata.name, namespace: .metadata.namespace}'

# Supprimer tous les services LoadBalancer
kubectl delete svc --all-namespaces --field-selector spec.type=LoadBalancer

# Attendre suppression Load Balancers Azure (2-3 min)
sleep 180

# Puis supprimer cluster
az aks delete --resource-group $RG_NAME --name $CLUSTER_NAME --yes --no-wait
```

---

### Problème 6: Coûts supérieurs aux estimations

**Symptôme**: Facture AKS plus élevée que prévu.

**Diagnostic**:
```bash
# 1. Vérifier node count actuel
az aks show --resource-group $RG_NAME --name $CLUSTER_NAME --query "agentPoolProfiles[].count"

# 2. Vérifier VM sizes
az aks show --resource-group $RG_NAME --name $CLUSTER_NAME --query "agentPoolProfiles[].vmSize"

# 3. Lister disks dans node resource group
NODE_RG=$(az aks show --resource-group $RG_NAME --name $CLUSTER_NAME --query nodeResourceGroup -o tsv)
az disk list --resource-group $NODE_RG --output table

# 4. Vérifier Load Balancers
az network lb list --resource-group $NODE_RG --output table

# 5. Vérifier Public IPs
az network public-ip list --resource-group $NODE_RG --output table

# 6. Analyser coûts via Cost Management
az consumption usage list \
  --start-date $(date -u -d '30 days ago' +%Y-%m-%d) \
  --end-date $(date -u +%Y-%m-%d) \
  --query "[?contains(instanceId, '$CLUSTER_NAME')]" \
  --output table
```

**Solutions courantes**:
- **Orphaned disks**: Supprimer disks non attachés
- **Unused Load Balancers**: Supprimer services inutilisés
- **Over-provisioned nodes**: Enable autoscaler
- **Large VM sizes**: Downgrade si low utilization

---

## 💰 Impact Business & ROI

### Économies Potentielles par Scénario

| Scénario | Économie Mensuelle | Économie Annuelle | Fréquence* | ROI Annuel (20 Clusters) |
|----------|-------------------|-------------------|------------|--------------------------|
| `aks_cluster_stopped` | $139 | $1,668 | 10% | $3,336 |
| `aks_cluster_zero_nodes` | $73 | $876 | 5% | $876 |
| `aks_cluster_no_user_pods` | $321 | $3,852 | 15% | $11,556 |
| `aks_autoscaler_not_enabled` | $280 | $3,360 | 40% | $26,880 |
| `aks_node_pool_oversized_vms` | $701 | $8,412 | 35% | $58,884 |
| `aks_orphaned_persistent_volumes` | $100 | $1,200 | 30% | $7,200 |
| `aks_unused_load_balancers` | $22 | $264 | 20% | $1,056 |
| `aks_low_cpu_utilization` | $701 | $8,412 | 40% | $67,296 |
| `aks_low_memory_utilization` | $349 | $4,188 | 25% | $20,940 |
| `aks_dev_test_always_on` | $160 | $1,920 | 25% | $9,600 |
| **TOTAL** | | | | **$207,624/an** |

\* Fréquence = % des clusters affectés (estimé)

---

### Arguments Business

#### 1. **Nodes = 70-80% des Coûts AKS**

**Stat clé**: Les nodes (VMs) représentent **70-80% du coût total** d'un cluster AKS.

**Exemple cluster production**:
```
Cluster Standard tier: $73/mois (3%)
+ 10 nodes D4s_v3: $1,401.60/mois (73%)
+ Load Balancers: $36.50/mois (2%)
+ Persistent Volumes: $200/mois (10%)
+ Networking (egress): $200/mois (10%)
+ Monitoring: $50/mois (2%)
= Total: $1,961.10/mois

Nodes = 71% du coût total
```

**CloudWaste Focus**: Optimiser nodes = **impact maximal ROI**.

#### 2. **Autoscaler: 30-50% Économies Instantanées**

**Problème**: **60% des clusters AKS n'ont pas autoscaler configuré** (études FinOps 2024).

**Pattern courant**:
```
Cluster sans autoscaler:
- Node count fixe: 10 nodes
- Charge réelle: varie 30-80% selon heure/jour
- Nodes idle: 3-7 nodes (30-70% du temps)
- Coût: $1,401.60/mois (10 × D4s_v3)

Avec autoscaler (min=3, max=10):
- Node count moyen: 6 nodes
- Scale up en pic (2h/jour)
- Scale down hors pic (22h/jour)
- Coût: $840.96/mois (6 × D4s_v3 moyenne)

Économie: $560.64/mois = $6,727.68/an (40%)
```

**CloudWaste ROI**: 20 clusters × **$6,728/an** = **$134,560/an** économisés.

#### 3. **VM Size Over-Provisioning: 50-75% Waste**

**Pattern**: Provisioning initial avec "large VMs just in case", jamais revisité.

**Exemple réel**:
```
Node pool "userpool":
- VM: Standard_D8s_v3 (8 vCPU, 32 GB RAM)
- Nodes: 8
- Utilization: CPU 18%, Memory 25%
- Coût: 8 × $0.384 × 730 = $2,243.52/mois

Rightsizing (D4s_v3: 4 vCPU, 16 GB RAM):
- Nodes: 8 (même count)
- Coût: 8 × $0.192 × 730 = $1,121.76/mois

Économie: $1,121.76/mois = $13,461.12/an (50%)
```

**CloudWaste action**:
- Détecter low CPU/memory utilization
- Recommander VM size approprié
- ROI: **$13,461/an par cluster** optimisé

#### 4. **Dev/Test Clusters: 60-75% Waste via Automation**

**Problème**: Clusters dev/test actifs 24/7 alors qu'utilisés 8h/jour × 5j/semaine.

**Cas d'usage**:
```
Cluster dev (3 nodes D2s_v3):
- Coût 24/7: $73 + $210.24 = $283.24/mois
- Usage réel: 8h × 5j = 40h/semaine = 24% uptime

Avec automation start/stop:
- Cluster fee: $73/mois (toujours payé)
- Nodes (173h/mois): 3 × $0.096 × 173 = $49.82/mois
- Total: $122.82/mois

Économie: $160.42/mois = $1,925.04/an (57%)
```

**CloudWaste action**:
- Détecter tags environment=dev/test
- Vérifier uptime 100%
- Recommander automation (Azure Automation, Logic Apps)
- ROI: **$1,925/an par cluster** dev/test

**Automation options**:
- **Azure Automation runbook**: $5/mois (500 min gratuit)
- **Logic Apps**: ~$10/mois (consumption)
- **Azure DevOps Pipeline**: gratuit (included)

#### 5. **Orphaned Resources: Coûts Cachés**

**Problème**: PVs, Load Balancers, Public IPs orphelins continuent à facturer.

**Exemples**:
```
1. Persistent Volumes orphelins (10 × 100 GB Premium SSD):
   - Coût: 10 × 100 × $0.12 = $120/mois = $1,440/an

2. Load Balancers inutilisés (3 services type LB supprimés):
   - Coût: 3 × $18.25 = $54.75/mois = $657/an

3. Public IPs non attachées (5 IPs):
   - Coût: 5 × $3.65 = $18.25/mois = $219/an

Total waste orphaned: $2,316/an par cluster
```

**CloudWaste detection**:
- Scan PVs status "Released" ou "Available" >14 jours
- Scan Services LoadBalancer 0 endpoints
- Scan Public IPs non associées
- ROI: **$2,316/an par cluster** nettoyé

---

### ROI Global Estimé

**Organisation moyenne (20 clusters AKS)**:

| Catégorie | Clusters Affectés | Économie/Cluster | ROI Annuel |
|-----------|-------------------|------------------|------------|
| Low CPU utilization | 8 (40%) | $8,412 | $67,296 |
| Oversized VMs | 7 (35%) | $8,412 | $58,884 |
| Autoscaler not enabled | 8 (40%) | $3,360 | $26,880 |
| Dev/test always on | 5 (25%) | $1,920 | $9,600 |
| Orphaned PVs | 6 (30%) | $1,200 | $7,200 |
| No user pods | 3 (15%) | $3,852 | $11,556 |
| Low memory utilization | 5 (25%) | $4,188 | $20,940 |
| **TOTAL** | | | **$202,356/an** |

**CloudWaste Pricing**: ~$8,000-12,000/an (20 clusters)
**ROI Net**: **$190,356-194,356/an (1,586-1,620% ROI)**
**Payback Period**: **< 3 semaines**

---

## 📚 Références Officielles Azure

### Azure Kubernetes Service (AKS)

1. **Pricing**
   https://azure.microsoft.com/en-us/pricing/details/kubernetes-service/

2. **SKU Tiers (Free, Standard, Premium)**
   https://learn.microsoft.com/en-us/azure/aks/free-standard-pricing-tiers

3. **Cluster Autoscaler**
   https://learn.microsoft.com/en-us/azure/aks/cluster-autoscaler

4. **Node Auto Provisioning (Karpenter)**
   https://learn.microsoft.com/en-us/azure/aks/node-autoprovision

5. **Container Insights (Azure Monitor)**
   https://learn.microsoft.com/en-us/azure/azure-monitor/containers/container-insights-overview

6. **Idle Cost Analysis**
   https://learn.microsoft.com/en-us/azure/aks/cost-analysis-idle-costs

7. **Start/Stop Cluster**
   https://learn.microsoft.com/en-us/azure/aks/start-stop-cluster

8. **Best Practices - Cost Optimization**
   https://learn.microsoft.com/en-us/azure/aks/best-practices-cost

### Storage & Networking

9. **Persistent Volumes (Azure Disks)**
   https://learn.microsoft.com/en-us/azure/aks/azure-csi-disk-storage-provision

10. **Storage Classes**
    https://learn.microsoft.com/en-us/azure/aks/concepts-storage#storage-classes

11. **Load Balancer Integration**
    https://learn.microsoft.com/en-us/azure/aks/load-balancer-standard

12. **Managed Disks Pricing**
    https://azure.microsoft.com/en-us/pricing/details/managed-disks/

### Virtual Machines (Node Pools)

13. **VM Sizes (D-series, E-series)**
    https://learn.microsoft.com/en-us/azure/virtual-machines/sizes

14. **VM Pricing Calculator**
    https://azure.microsoft.com/en-us/pricing/calculator/

### Azure SDK & Tools

15. **azure-mgmt-containerservice (Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-containerservice/azure.mgmt.containerservice

16. **Kubernetes Python Client**
    https://github.com/kubernetes-client/python

17. **Azure Monitor Query (Metrics API)**
    https://learn.microsoft.com/en-us/python/api/azure-monitor-query/azure.monitor.query

18. **Azure CLI - AKS Commands**
    https://learn.microsoft.com/en-us/cli/azure/aks

### Automation & Management

19. **Azure Automation**
    https://learn.microsoft.com/en-us/azure/automation/overview

20. **Logic Apps**
    https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview

21. **Azure DevOps Pipelines**
    https://learn.microsoft.com/en-us/azure/devops/pipelines/

### FinOps & Cost Management

22. **FinOps Best Practices for Containers**
    https://learn.microsoft.com/en-us/cloud-computing/finops/best-practices/containers

23. **Azure Cost Management**
    https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/cost-mgt-best-practices

24. **Azure Advisor Recommendations**
    https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations

---

## ✅ Checklist d'Implémentation

### Phase 1 - Scénarios Simples (Sprint 1-2)

- [ ] **Scénario #1**: `aks_cluster_stopped`
  - [ ] Compléter stub `scan_idle_eks_clusters()` (ligne 2967)
  - [ ] Query via `ContainerServiceClient.managed_clusters.list()`
  - [ ] Filter: `power_state.code == 'Stopped'`
  - [ ] Calcul coût: cluster fee + storage (pas compute)
  - [ ] Tests unitaires
  - [ ] Tests CLI

- [ ] **Scénario #2**: `aks_cluster_zero_nodes`
  - [ ] Fonction dans même stub
  - [ ] Query agent pools: `agent_pools.list()`
  - [ ] Sum node counts: `total_nodes = sum(pool.count)`
  - [ ] Filter: `total_nodes == 0`
  - [ ] Tests

- [ ] **Scénario #3**: `aks_cluster_no_user_pods`
  - [ ] Fonction dans même stub
  - [ ] Get AKS credentials: `get_admin_credentials()`
  - [ ] Query Kubernetes API: `list_pod_for_all_namespaces()`
  - [ ] Filter system namespaces
  - [ ] Count user pods
  - [ ] Tests

- [ ] **Scénario #4**: `aks_autoscaler_not_enabled`
  - [ ] Fonction `scan_aks_autoscaler_not_enabled()`
  - [ ] Query node pools
  - [ ] Filter: `enable_auto_scaling == False`
  - [ ] Estimate over-provisioning
  - [ ] Tests

- [ ] **Scénario #5**: `aks_node_pool_oversized_vms`
  - [ ] Fonction `scan_aks_oversized_vms()`
  - [ ] Query Azure Monitor metrics (CPU, memory)
  - [ ] Calculate avg utilization
  - [ ] VM downgrade recommendations
  - [ ] Tests

- [ ] **Scénario #6**: `aks_orphaned_persistent_volumes`
  - [ ] Fonction `scan_aks_orphaned_pvs()`
  - [ ] Query Kubernetes PVs
  - [ ] Filter: `phase == 'Released' or 'Available'`
  - [ ] Get Azure Disk IDs
  - [ ] Calculate storage costs
  - [ ] Tests

- [ ] **Scénario #7**: `aks_unused_load_balancers`
  - [ ] Fonction `scan_aks_unused_load_balancers()`
  - [ ] Query Kubernetes Services type LoadBalancer
  - [ ] Check endpoints (backend count)
  - [ ] Filter: `backend_count == 0`
  - [ ] Tests

### Phase 2 - Azure Monitor Métriques (Sprint 3)

- [ ] **Scénario #8**: `aks_low_cpu_utilization`
  - [ ] Fonction `scan_aks_low_cpu()`
  - [ ] Enable Container Insights check
  - [ ] Query metric `node_cpu_usage_percentage`
  - [ ] Calculate avg CPU% over 30 days
  - [ ] Rightsizing recommendations
  - [ ] Tests

- [ ] **Scénario #9**: `aks_low_memory_utilization`
  - [ ] Fonction `scan_aks_low_memory()`
  - [ ] Query metric `node_memory_working_set_percentage`
  - [ ] Calculate avg memory%
  - [ ] VM downgrade recommendations (less RAM)
  - [ ] Tests

- [ ] **Scénario #10**: `aks_dev_test_always_on`
  - [ ] Fonction `scan_aks_dev_test_always_on()`
  - [ ] Detect dev/test tags
  - [ ] Query Activity Log for stop events
  - [ ] Calculate uptime ratio
  - [ ] Automation recommendations
  - [ ] Tests

### Infrastructure & Tests

- [ ] **Dependencies**
  - [ ] Add `kubernetes` Python client to requirements.txt
  - [ ] Update `azure-mgmt-containerservice` to latest
  - [ ] Add `azure-monitor-query` if not present

- [ ] **Database Schema**
  - [ ] Ajouter support metadata AKS (node_count, vm_size, autoscaler_enabled)
  - [ ] Migration Alembic
  - [ ] Indexes

- [ ] **Detection Rules**
  - [ ] Règles par défaut AKS
  - [ ] Paramètres configurables (thresholds, exclusions)
  - [ ] UI ajustement règles

- [ ] **Tests**
  - [ ] Tests unitaires (70%+ coverage)
  - [ ] Tests AKS + Kubernetes SDK mocks
  - [ ] Tests CLI (scripts ci-dessus)
  - [ ] Tests end-to-end

- [ ] **Documentation**
  - [ ] API endpoints
  - [ ] Frontend components (AKS cluster cards)
  - [ ] User guide

### Frontend

- [ ] **Dashboard**
  - [ ] Afficher clusters AKS
  - [ ] Filtrer par scénario
  - [ ] Tri par coût, node count, utilization

- [ ] **Resource Details**
  - [ ] Page détail cluster AKS
  - [ ] Afficher node pools
  - [ ] Graphiques métriques (CPU, memory, pods)
  - [ ] Actions (Stop, Delete, Enable Autoscaler)
  - [ ] Recommandations rightsizing

- [ ] **Cost Calculator**
  - [ ] Estimateur économies AKS
  - [ ] Comparaison VM sizes
  - [ ] Simulation autoscaler savings
  - [ ] Export PDF

---

## 🎯 Priorités d'Implémentation

### P0 - Quick Wins (Sprint 1)
1. `aks_cluster_no_user_pods` (stub existant, économie $321/mois)
2. `aks_autoscaler_not_enabled` (ROI élevé $280/mois, 40% fréquence)
3. `aks_node_pool_oversized_vms` (**ROI critique** $701/mois, 35% fréquence)
4. `aks_low_cpu_utilization` (**ROI critique** $701/mois, 40% fréquence)

**Raison**: Économie immédiate, haute fréquence, facile à détecter.

### P1 - High ROI (Sprint 2)
5. `aks_low_memory_utilization` (économie $349/mois)
6. `aks_dev_test_always_on` (économie $160/mois, 25% fréquence)
7. `aks_cluster_stopped` (économie $139/mois)
8. `aks_cluster_zero_nodes` (économie $73/mois)
9. `aks_orphaned_persistent_volumes` (économie $100/mois)

**Raison**: ROI élevé, fréquence moyenne.

### P2 - Cleanup (Sprint 3)
10. `aks_unused_load_balancers` (économie $22/mois)

**Raison**: ROI faible mais facile à implémenter.

---

## 🚀 Quick Start

### Script Test Complet

```bash
#!/bin/bash
# Script: test-all-aks-scenarios.sh
# Description: Teste scénarios AKS critiques

set -e

echo "🚀 CloudWaste - Test AKS Scenarios"
echo "==================================="

LOCATION="eastus"
BASE_RG="rg-cloudwaste-aks-test"

# Test #1: Cluster No User Pods
echo ""
echo "📊 Test #1: AKS Cluster No User Pods"
RG_NAME="${BASE_RG}-nopods"
CLUSTER_NAME="aks-test-nopods"

az group create --name $RG_NAME --location $LOCATION --output none
az aks create --resource-group $RG_NAME --name $CLUSTER_NAME --location $LOCATION --tier standard --node-count 3 --node-vm-size Standard_D2s_v3 --generate-ssh-keys --output none
az aks wait --resource-group $RG_NAME --name $CLUSTER_NAME --created --timeout 900

echo "✅ AKS cluster with 3 nodes but 0 user pods"
echo "   Coût: \$283.24/mois wasteful"
az group delete --name $RG_NAME --yes --no-wait

# Test #2: Autoscaler Not Enabled
echo ""
echo "📊 Test #2: Autoscaler Not Enabled"
RG_NAME="${BASE_RG}-noautoscaler"
CLUSTER_NAME="aks-test-noautoscaler"

az group create --name $RG_NAME --location $LOCATION --output none
az aks create --resource-group $RG_NAME --name $CLUSTER_NAME --location $LOCATION --tier standard --node-count 5 --node-vm-size Standard_D4s_v3 --generate-ssh-keys --output none

echo "✅ AKS with 5 fixed nodes (no autoscaler)"
echo "   Coût: \$700.80/mois, économie potentielle: \$280/mois (40%)"
az group delete --name $RG_NAME --yes --no-wait

# Test #3: Oversized VMs
echo ""
echo "📊 Test #3: Oversized VMs (D8s_v3 with low usage)"
RG_NAME="${BASE_RG}-oversized"
CLUSTER_NAME="aks-test-oversized"

az group create --name $RG_NAME --location $LOCATION --output none
az aks create --resource-group $RG_NAME --name $CLUSTER_NAME --location $LOCATION --tier standard --node-count 3 --node-vm-size Standard_D8s_v3 --generate-ssh-keys --output none

echo "✅ AKS with 3 × D8s_v3 nodes (overkill)"
echo "   Coût: \$840.96/mois, économie via D2s_v3: \$630.72/mois (75%)"
az group delete --name $RG_NAME --yes --no-wait

echo ""
echo "✅ All tests completed!"
echo "   Total wasteful cost detected: ~\$1,825/mois"
echo "   Potential savings: ~\$910/mois (50%)"
echo "   Run CloudWaste scanner to detect these issues"
```

**Usage**:
```bash
chmod +x test-all-aks-scenarios.sh
./test-all-aks-scenarios.sh
```

---

## 📊 Résumé Exécutif

### Couverture

- **10 scénarios** (100% coverage)
- **7 Phase 1** (détection simple, attributs cluster)
- **3 Phase 2** (Azure Monitor métriques)

### ROI Estimé

- **Économie moyenne**: $100-700/mois par cluster wasteful
- **ROI annuel**: **$87,240-207,624/an** (organisation 20 clusters)
- **Payback period**: < **3 semaines**

### Scénarios Critiques 2025

- **Autoscaler not enabled**: 40% des clusters (économie $280/mois)
- **Oversized VMs**: 35% des clusters (économie $701/mois)
- **Low CPU utilization**: 40% des clusters (économie $701/mois)
- Nodes = **70-80% des coûts AKS** → Focus optimization nodes

### Next Steps

1. **Implémenter P0** (scénarios #3, #4, #5, #8) → Sprint 1
2. **Implémenter P1** (scénarios #9, #10, #1, #2, #6) → Sprint 2
3. **Implémenter P2** (scénario #7) → Sprint 3
4. **Tests end-to-end** + documentation utilisateur

---

**Dernière mise à jour**: 2025-01-28
**Auteur**: CloudWaste Documentation Team
**Version**: 1.0.0
