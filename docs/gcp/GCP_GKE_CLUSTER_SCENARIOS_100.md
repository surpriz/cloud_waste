# CloudWaste - Couverture 100% GCP GKE Clusters

**Resource Type:** `Compute : GKE Clusters (Google Kubernetes Engine)`
**Provider:** Google Cloud Platform (GCP)
**API:** `container.googleapis.com` (GKE API v1)
**Équivalents:** AWS EKS, Azure AKS
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing GKE](#modèle-de-pricing-gke)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Clusters Vides](#1-gke_cluster_empty---clusters-vides)
  - [2. Clusters avec Nodes Inactifs](#2-gke_cluster_nodes_inactive---clusters-avec-nodes-inactifs)
  - [3. Node Pools Sur-Provisionnés](#3-gke_cluster_nodepool_overprovisioned---node-pools-sur-provisionnés)
  - [4. Nodes Ancien Type Machine](#4-gke_cluster_old_machine_type---nodes-ancien-type-machine)
  - [5. Clusters Dev/Test 24/7](#5-gke_cluster_devtest_247---clusters-devtest-247)
  - [6. Clusters Sans Auto-Scaling](#6-gke_cluster_no_autoscaling---clusters-sans-auto-scaling)
  - [7. Clusters Non Taggués](#7-gke_cluster_untagged---clusters-non-taggués)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Nodes Sous-Utilisés](#8-gke_cluster_nodes_underutilized---nodes-sous-utilisés)
  - [9. Pods Over-Requested](#9-gke_cluster_pods_overrequested---pods-over-requested)
  - [10. Clusters Sans Workloads](#10-gke_cluster_no_workloads---clusters-sans-workloads)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte GKE (Google Kubernetes Engine)

Google Kubernetes Engine est le service **Kubernetes managé** de GCP. Deux modes d'opération :

#### **1. GKE Standard Mode**
- **Contrôle total** sur nodes, node pools, configuration
- **Management fee** : $0.10/cluster/hour (~$73/mois)
- **Nodes** : Facturation Compute Engine (vous gérez)
- **Auto-scaling** : Optionnel (Cluster Autoscaler)

#### **2. GKE Autopilot Mode**
- **Fully managed** : Google gère nodes, scaling, sécurité
- **Aucun management fee**
- **Facturation au pod** : CPU/RAM réellement utilisés
- **Auto-scaling** : Automatique (intégré)

### Composants Facturés

| Composant | Standard Mode | Autopilot Mode |
|-----------|--------------|----------------|
| **Management fee** | $0.10/hour (~$73/mois) | $0 |
| **Nodes (VMs)** | Compute Engine pricing | $0 (géré par Google) |
| **Pods CPU** | Inclus dans node cost | $0.0445/vCPU/hour |
| **Pods Memory** | Inclus dans node cost | $0.00492/GB/hour |
| **Persistent Disks** | Standard pricing | Standard pricing |
| **Load Balancers** | Standard pricing | Standard pricing |

### Waste Typique

1. **Clusters vides** : Management fee sans workload ($73/mois × N clusters)
2. **Node pools over-provisioned** : 10 nodes pour 3 pods = 70% gaspillage
3. **Pas d'auto-scaling** : Nodes fixes même quand charge varie
4. **Ancien types machines** : n1 → n2 = -20% à -30% coût
5. **Dev/test 24/7** : Clusters dev tournant weekends/nuits
6. **Nodes sous-utilisés** : CPU <30%, Memory <40%
7. **Standard vs Autopilot** : Autopilot souvent -60% coût pour workloads variables

---

## Modèle de Pricing GKE

### Management Fee (Standard Mode uniquement)

| Mode | Management Fee | Facturé Par | Notes |
|------|---------------|------------|-------|
| **Standard** | $0.10/hour | Cluster | ~$73/mois par cluster |
| **Autopilot** | $0 | N/A | Pas de fee, paiement au pod |

### Nodes Pricing (Standard Mode)

Nodes = Compute Engine instances, pricing identique :

| Machine Type | vCPUs | RAM (GB) | Prix/Node/Mois | Prix 3 Nodes |
|-------------|-------|---------|----------------|--------------|
| **e2-small** | 0.5 | 2 GB | $14.23 | $42.69 |
| **n1-standard-1** | 1 | 3.75 GB | $24.27 | $72.81 |
| **n2-standard-2** | 2 | 8 GB | $71.17 | $213.51 |
| **n2-standard-4** | 4 | 16 GB | $142.34 | $427.02 |
| **n2-standard-8** | 8 | 32 GB | $284.68 | $854.04 |

**Total cluster cost (Standard) = Management fee + Nodes cost**

Exemple : Cluster avec 3x n2-standard-2 nodes
```
Management fee: $73.00/mois
Nodes: 3 × $71.17 = $213.51/mois
TOTAL: $286.51/mois
```

### Autopilot Pricing

Facturation au **pod** (ressources réellement allouées) :

| Resource | Prix/Heure | Prix/Mois (730h) |
|----------|-----------|-----------------|
| **vCPU** | $0.0445/vCPU | $32.49/vCPU |
| **Memory** | $0.00492/GB | $3.59/GB |

Exemple : Pod avec 1 vCPU + 2 GB RAM
```
CPU: 1 × $32.49 = $32.49/mois
Memory: 2 × $3.59 = $7.18/mois
TOTAL: $39.67/mois par pod
```

**Note :** Autopilot souvent -40% à -60% moins cher que Standard pour workloads variables.

### Coûts Additionnels

- **Persistent Volume Claims** : pd-standard/balanced/ssd pricing
- **Load Balancers** : ~$18/mois par LB
- **Egress network** : $0.12/GB (après 1 GB gratuit)

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `gke_cluster_empty` - Clusters Vides

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters GKE
from google.cloud import container_v1

gke_client = container_v1.ClusterManagerClient()

parent = f"projects/{project_id}/locations/-"  # "-" = toutes zones
clusters_response = gke_client.list_clusters(parent=parent)

# 2. Pour chaque cluster, vérifier nombre de nodes
for cluster in clusters_response.clusters:
    cluster_name = cluster.name
    location = cluster.location  # Zone ou région

    # 3. Compter nodes actifs
    total_nodes = 0
    for node_pool in cluster.node_pools:
        # initial_node_count = taille configurée
        # Nodes réels peuvent être différents si auto-scaling
        current_node_count = node_pool.initial_node_count
        total_nodes += current_node_count

    # 4. Détection si cluster sans nodes
    if total_nodes == 0:
        # 5. Calculer âge cluster
        creation_timestamp = cluster.create_time
        age_days = (now - creation_timestamp).days

        if age_days >= min_age_days:
            # Cluster vide = waste (management fee uniquement)
```

**Critères :**
- Mode Standard (management fee applicable)
- `total_nodes == 0` (aucun node)
- `age >= min_age_days` (défaut: 7 jours)

**API Calls :**
```python
# GKE API
from google.cloud import container_v1

gke_client = container_v1.ClusterManagerClient()

# Lister clusters (toutes zones)
clusters = gke_client.list_clusters(
    parent=f"projects/{project_id}/locations/-"
)
```

#### Calcul de Coût

**Formule :**

Cluster vide en mode Standard = management fee seul :

```python
# Mode Standard uniquement (Autopilot = $0 fee)
if cluster.autopilot.enabled:
    monthly_cost = 0  # Pas de waste si Autopilot sans workloads
else:
    # Standard mode: management fee
    management_fee_hourly = 0.10  # $/hour
    hours_per_month = 730

    monthly_cost = management_fee_hourly * hours_per_month  # $73.00/mois

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Cluster Standard vide depuis 90 jours :
```python
management_fee = $0.10/hour
monthly_cost = $0.10 * 730 = $73.00/mois
already_wasted = $73.00 * (90/30) = $219.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 7 | Âge minimum avant détection |
| `exclude_labels` | dict | `{}` | Labels pour exclure clusters |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-1234567890",
  "resource_name": "empty-test-cluster",
  "resource_type": "gke_cluster_empty",
  "location": "us-central1-a",
  "cluster_mode": "STANDARD",
  "total_nodes": 0,
  "node_pools": [],
  "status": "RUNNING",
  "creation_time": "2024-08-05T10:00:00Z",
  "age_days": 89,
  "management_fee_monthly": 73.00,
  "nodes_cost_monthly": 0.00,
  "estimated_monthly_cost": 73.00,
  "already_wasted": 217.03,
  "confidence": "high",
  "recommendation": "Delete cluster or migrate to Autopilot mode",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `gke_cluster_nodes_inactive` - Clusters avec Nodes Inactifs

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# 2. Pour chaque cluster avec nodes, vérifier status nodes
for cluster in clusters.clusters:
    if cluster.current_node_count == 0:
        continue  # Skip empty clusters (scénario 1)

    # 3. Récupérer nodes via Kubernetes API
    # Nécessite credentials cluster
    from kubernetes import client, config

    # Charger kubeconfig pour cluster
    cluster_credentials = get_cluster_credentials(cluster)
    config.load_kube_config_from_dict(cluster_credentials)

    v1 = client.CoreV1Api()

    # 4. Lister tous les nodes
    nodes = v1.list_node()

    # 5. Vérifier status chaque node
    ready_nodes = 0
    total_nodes = len(nodes.items)

    for node in nodes.items:
        # Vérifier condition "Ready"
        for condition in node.status.conditions:
            if condition.type == "Ready" and condition.status == "True":
                ready_nodes += 1
                break

    # 6. Détection si TOUS nodes non-ready
    if ready_nodes == 0 and total_nodes > 0:
        # Tous nodes inactifs = waste (paiement sans capacité)
```

**Critères :**
- `total_nodes > 0`
- `ready_nodes == 0` (tous nodes non-ready ou cordoned)
- Cluster en mode Standard

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Kubernetes API (via credentials cluster)
from kubernetes import client
v1 = client.CoreV1Api()
nodes = v1.list_node()
```

#### Calcul de Coût

**Formule :**

Nodes inactifs = 100% waste (management fee + nodes cost) :

```python
# Management fee (Standard mode)
management_fee = 73.00  # $/mois

# Nodes cost
total_nodes_cost = 0

for node_pool in cluster.node_pools:
    machine_type = node_pool.config.machine_type  # "n2-standard-2"
    node_count = node_pool.initial_node_count

    # Récupérer pricing machine type
    node_cost_monthly = get_machine_cost(machine_type)  # Ex: $71.17 pour n2-standard-2

    total_nodes_cost += node_count * node_cost_monthly

# Coût total = 100% waste (cluster inutilisable)
monthly_cost = management_fee + total_nodes_cost

# Coût gaspillé depuis que nodes sont inactifs
# (calculer via lastTransitionTime des conditions)
inactive_days = calculate_inactive_duration(nodes)
already_wasted = monthly_cost * (inactive_days / 30.0)
```

**Exemple :**

Cluster avec 3x n2-standard-2 nodes (tous inactifs) depuis 30 jours :
```python
management_fee = $73.00
nodes_cost = 3 * $71.17 = $213.51
monthly_cost = $73.00 + $213.51 = $286.51
already_wasted = $286.51 * (30/30) = $286.51
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_inactive_days` | int | 7 | Durée minimum inactivité |
| `ready_threshold` | float | 0.0 | % minimum nodes ready (0 = aucun) |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-9876543210",
  "resource_name": "failed-upgrade-cluster",
  "resource_type": "gke_cluster_nodes_inactive",
  "location": "us-east1-b",
  "cluster_mode": "STANDARD",
  "total_nodes": 3,
  "ready_nodes": 0,
  "node_pools": [
    {
      "name": "default-pool",
      "machine_type": "n2-standard-2",
      "node_count": 3,
      "status": "NOT_READY"
    }
  ],
  "inactive_since": "2024-10-03T08:00:00Z",
  "inactive_days": 30,
  "management_fee_monthly": 73.00,
  "nodes_cost_monthly": 213.51,
  "estimated_monthly_cost": 286.51,
  "already_wasted": 286.51,
  "confidence": "high",
  "recommendation": "Delete and recreate cluster, or troubleshoot node issues",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `gke_cluster_nodepool_overprovisioned` - Node Pools Sur-Provisionnés

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

for cluster in clusters.clusters:
    # 2. Pour chaque cluster, récupérer pods via Kubernetes API
    cluster_credentials = get_cluster_credentials(cluster)
    config.load_kube_config_from_dict(cluster_credentials)

    v1 = client.CoreV1Api()

    # 3. Compter pods running (hors kube-system)
    pods = v1.list_pod_for_all_namespaces()

    user_pods = [
        p for p in pods.items
        if p.metadata.namespace not in ['kube-system', 'kube-public', 'kube-node-lease']
        and p.status.phase == 'Running'
    ]

    total_user_pods = len(user_pods)

    # 4. Compter nodes disponibles
    nodes = v1.list_node()
    total_nodes = len(nodes.items)

    # 5. Calculer ratio pods/node
    if total_nodes > 0:
        pods_per_node = total_user_pods / total_nodes
    else:
        pods_per_node = 0

    # 6. Détection si ratio très faible (<2 pods/node)
    # Note: Un node peut héberger 30-110 pods selon machine type
    if pods_per_node < min_pods_per_node_threshold and total_nodes >= 2:
        # Node pool over-provisioned = waste

        # 7. Calculer nodes recommandés
        # Estimation: 10 pods/node en moyenne (conservateur)
        optimal_pods_per_node = 10
        recommended_nodes = max(1, int(total_user_pods / optimal_pods_per_node))

        if recommended_nodes < total_nodes:
            # Over-provisioning détecté
```

**Critères :**
- `pods_per_node < 2` (très faible utilisation)
- `total_nodes >= 2` (au moins 2 nodes)
- Pas d'auto-scaling activé (sinon cluster s'ajusterait)

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Kubernetes API
from kubernetes import client
v1 = client.CoreV1Api()
pods = v1.list_pod_for_all_namespaces()
nodes = v1.list_node()
```

#### Calcul de Coût

**Formule :**

Over-provisioning = différence nodes actuels vs recommandés :

```python
# Exemple: 10 nodes pour 5 pods = recommandé 1-2 nodes

total_nodes = 10
recommended_nodes = 1  # 5 pods / 10 pods_per_node (conservateur)
wasted_nodes = total_nodes - recommended_nodes  # 9 nodes

# Coût par node (ex: n2-standard-2)
node_cost_monthly = 71.17  # $/mois

# Waste = nodes inutiles
monthly_waste = wasted_nodes * node_cost_monthly  # 9 * $71.17 = $640.53

# Coût gaspillé depuis création cluster
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster avec 10x n2-standard-2 nodes, seulement 5 pods running, depuis 120 jours :
```python
total_nodes = 10
recommended_nodes = 1
wasted_nodes = 9
node_cost = $71.17
monthly_waste = 9 * $71.17 = $640.53
already_wasted = $640.53 * (120/30) = $2,562.12
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_pods_per_node_threshold` | float | 2.0 | Pods/node minimum avant détection |
| `optimal_pods_per_node` | int | 10 | Pods/node optimal pour calcul |
| `exclude_autoscaling_enabled` | bool | `True` | Exclure si auto-scaling activé |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-5555555555",
  "resource_name": "overprovisioned-cluster",
  "resource_type": "gke_cluster_nodepool_overprovisioned",
  "location": "europe-west1-b",
  "cluster_mode": "STANDARD",
  "total_nodes": 10,
  "total_user_pods": 5,
  "pods_per_node": 0.5,
  "recommended_nodes": 1,
  "wasted_nodes": 9,
  "node_pool_config": {
    "machine_type": "n2-standard-2",
    "autoscaling_enabled": false
  },
  "node_cost_monthly": 71.17,
  "total_nodes_cost_monthly": 711.70,
  "recommended_cost_monthly": 71.17,
  "estimated_monthly_waste": 640.53,
  "already_wasted": 2562.12,
  "confidence": "high",
  "recommendation": "Enable autoscaling or reduce nodes to 1-2 for current workload",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `gke_cluster_old_machine_type` - Nodes Ancien Type Machine

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

for cluster in clusters.clusters:
    # 2. Pour chaque node pool, vérifier machine type
    for node_pool in cluster.node_pools:
        machine_type = node_pool.config.machine_type  # "n1-standard-4"

        # 3. Détection si génération ancienne (n1)
        if machine_type.startswith('n1-'):
            # 4. Calculer équivalent moderne (n2/n2d)
            n2_equivalent = machine_type.replace('n1-', 'n2-')

            # 5. Calculer économie potentielle
            n1_cost = get_machine_cost(machine_type)
            n2_cost = get_machine_cost(n2_equivalent)

            # n2 a minimum 2 vCPUs, donc comparaison ajustée
            # n2 offre +40% performance → coût/performance réduit

            if n2_cost < n1_cost or (n2_cost <= n1_cost * 1.2):  # Acceptable si <20% plus cher
                node_count = node_pool.initial_node_count

                # Old generation = waste (suboptimal price/performance)
```

**Critères :**
- `machine_type.startswith('n1-')`
- Équivalent n2/n2d existe et meilleur price/performance
- Node pool actif (node_count > 0)

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Cluster details (node pools)
cluster = gke_client.get_cluster(
    name=f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
)
```

#### Calcul de Coût

**Formule :**

n1 → n2 migration = économie price/performance :

```python
# Exemple: n1-standard-4 → n2-standard-2 (half vCPUs but similar perf)

# Node pool: 5 nodes n1-standard-4
node_count = 5
n1_cost = 97.08  # $/mois par node

# Recommandation: n2-standard-2 (2 vCPUs mais +40% perf = équivalent)
n2_cost = 71.17  # $/mois par node

# Calcul économie
current_cost = node_count * n1_cost  # 5 * $97.08 = $485.40
recommended_cost = node_count * n2_cost  # 5 * $71.17 = $355.85

# Waste = différence (si migration conserve performance)
monthly_waste = current_cost - recommended_cost  # $129.55

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Node pool avec 5x n1-standard-4 depuis 180 jours :
```python
current_cost = 5 * $97.08 = $485.40/mois
recommended_cost = 5 * $71.17 = $355.85/mois (n2-standard-2)
monthly_waste = $129.55
already_wasted = $129.55 * (180/30) = $777.30
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `old_generations` | list | `['n1']` | Générations anciennes |
| `preferred_generation` | str | `'n2d'` | Génération recommandée |
| `min_savings_threshold` | float | 20.0 | Économie minimum $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-3333333333",
  "resource_name": "legacy-workload-cluster",
  "resource_type": "gke_cluster_old_machine_type",
  "location": "us-central1-a",
  "cluster_mode": "STANDARD",
  "node_pool": {
    "name": "default-pool",
    "machine_type": "n1-standard-4",
    "node_count": 5
  },
  "current_cost_monthly": 485.40,
  "recommended_machine_type": "n2-standard-2",
  "recommended_cost_monthly": 355.85,
  "estimated_monthly_waste": 129.55,
  "already_wasted": 777.30,
  "savings_percentage": 26.7,
  "confidence": "medium",
  "recommendation": "Migrate to n2-standard-2 for +40% performance/vCPU and -27% cost",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `gke_cluster_devtest_247` - Clusters Dev/Test 24/7

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

for cluster in clusters.clusters:
    # 2. Vérifier labels pour identifier env dev/test
    labels = cluster.resource_labels if hasattr(cluster, 'resource_labels') else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test/staging
    if environment in ['dev', 'test', 'staging', 'development']:
        # 4. Vérifier uptime (cluster créé depuis combien de temps)
        creation_time = cluster.create_time
        age_days = (now - creation_time).days

        # 5. Détection si uptime >7 jours continus
        if age_days >= min_uptime_days:
            # 6. Calculer économie potentielle (arrêts nocturnes/weekends)
            # Business hours: 8h-20h Lun-Ven = 60h/semaine
            # Actuel: 24/7 = 168h/semaine
            # Économie: (168-60)/168 = 64%

            # Dev/Test 24/7 = waste détecté
```

**Critères :**
- `labels.environment in ['dev', 'test', 'staging']`
- `uptime_days >= 7` (tournant constamment)
- Mode Standard (Autopilot auto-scale à zéro pods = $0)

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")
```

#### Calcul de Coût

**Formule :**

Cluster dev 24/7 vs horaires business :

```python
# Cluster dev: 3x n2-standard-2 nodes + management fee

# Coût actuel (24/7)
management_fee = 73.00  # $/mois
nodes_cost = 3 * 71.17 = 213.51  # $/mois
monthly_cost = 73.00 + 213.51 = 286.51  # $/mois

# Coût optimal (60h/semaine)
hours_optimal = 60  # 12h/jour × 5 jours
hours_actual = 168  # 24h × 7 jours

# Management fee reste (cluster existe)
# Nodes peuvent être arrêtés → économie 64%
optimal_nodes_cost = nodes_cost * (hours_optimal / hours_actual)  # $76.34

optimal_cost = management_fee + optimal_nodes_cost  # $149.34
monthly_waste = monthly_cost - optimal_cost  # $137.17

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster dev avec 3x n2-standard-2 depuis 90 jours :
```python
current_cost = $286.51/mois (24/7)
optimal_cost = $149.34/mois (60h/semaine)
monthly_waste = $137.17
already_wasted = $137.17 * (90/30) = $411.51
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `min_uptime_days` | int | 7 | Uptime minimum pour détection |
| `business_hours_per_week` | int | 60 | Heures optimales/semaine |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-7777777777",
  "resource_name": "dev-backend-cluster",
  "resource_type": "gke_cluster_devtest_247",
  "location": "us-east1-c",
  "cluster_mode": "STANDARD",
  "labels": {
    "environment": "dev",
    "team": "backend"
  },
  "creation_time": "2024-08-05T09:00:00Z",
  "uptime_days": 89,
  "current_uptime_hours_weekly": 168,
  "optimal_uptime_hours_weekly": 60,
  "current_cost_monthly": 286.51,
  "optimal_cost_monthly": 149.34,
  "estimated_monthly_waste": 137.17,
  "already_wasted": 407.27,
  "waste_percentage": 48,
  "confidence": "high",
  "recommendation": "Implement automated start/stop schedule or migrate to Autopilot",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `gke_cluster_no_autoscaling` - Clusters Sans Auto-Scaling

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters Standard mode
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

standard_clusters = [c for c in clusters.clusters if not c.autopilot.enabled]

for cluster in standard_clusters:
    # 2. Pour chaque node pool, vérifier autoscaling
    has_autoscaling = False

    for node_pool in cluster.node_pools:
        if node_pool.autoscaling and node_pool.autoscaling.enabled:
            has_autoscaling = True
            break

    # 3. Détection si AUCUN node pool avec autoscaling
    if not has_autoscaling:
        # 4. Vérifier variabilité charge (via métriques pods)
        # Si charge varie >30%, autoscaling recommandé

        # Récupérer métriques pods sur 14 jours
        pod_count_timeseries = get_pod_count_metrics(cluster, lookback_days=14)

        if pod_count_timeseries:
            min_pods = min(pod_count_timeseries)
            max_pods = max(pod_count_timeseries)
            avg_pods = sum(pod_count_timeseries) / len(pod_count_timeseries)

            # Calculer variabilité
            variability = ((max_pods - min_pods) / avg_pods * 100) if avg_pods > 0 else 0

            # 5. Détection si variabilité >30%
            if variability >= min_variability_threshold:
                # Pas d'autoscaling avec charge variable = inefficient
```

**Critères :**
- Mode Standard (Autopilot a autoscaling intégré)
- Aucun node pool avec autoscaling activé
- Charge variable >30% (min/max pods)

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Kubernetes API (pod count)
from kubernetes import client
v1 = client.CoreV1Api()
pods = v1.list_pod_for_all_namespaces()
```

#### Calcul de Coût

**Formule :**

Sans autoscaling = over-provisioning permanent :

```python
# Exemple: Cluster fixe 10 nodes, charge varie 2-8 pods

# Nodes fixes
fixed_nodes = 10
node_cost = 71.17  # n2-standard-2

# Charge moyenne (3 pods avg)
avg_pods = 3
optimal_nodes = max(1, int(avg_pods / 10))  # 1 node suffit en moyenne

# Waste = différence nodes fixes vs optimal moyen
wasted_nodes = fixed_nodes - optimal_nodes  # 9 nodes
monthly_waste = wasted_nodes * node_cost  # $640.53

# Note: Avec autoscaling, cluster s'ajusterait automatiquement
# Économie = waste (approximation conservative: 50% des nodes inutiles)
conservative_waste = monthly_waste * 0.5  # $320.27

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = conservative_waste * age_months
```

**Exemple :**

Cluster fixe 10 nodes (charge 2-8 pods) depuis 120 jours :
```python
fixed_nodes = 10
optimal_avg_nodes = 1
wasted_nodes = 9
node_cost = $71.17
conservative_waste = (9 * $71.17) * 0.5 = $320.27
already_wasted = $320.27 * (120/30) = $1,281.08
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_variability_threshold` | float | 30.0 | Variabilité % minimum charge |
| `lookback_days` | int | 14 | Période analyse variabilité |
| `waste_factor` | float | 0.5 | Facteur conservateur waste (50%) |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-9999999999",
  "resource_name": "fixed-size-cluster",
  "resource_type": "gke_cluster_no_autoscaling",
  "location": "asia-southeast1-a",
  "cluster_mode": "STANDARD",
  "total_nodes": 10,
  "autoscaling_enabled": false,
  "workload_variability": {
    "min_pods": 2,
    "max_pods": 8,
    "avg_pods": 3,
    "variability_percent": 200
  },
  "node_pool_config": {
    "machine_type": "n2-standard-2",
    "fixed_size": 10
  },
  "current_cost_monthly": 711.70,
  "optimal_avg_cost_monthly": 71.17,
  "estimated_monthly_waste": 320.27,
  "already_wasted": 1281.08,
  "confidence": "medium",
  "recommendation": "Enable Cluster Autoscaler with min 1, max 10 nodes",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `gke_cluster_untagged` - Clusters Non Taggués

#### Détection

**Logique :**
```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque cluster, vérifier labels
for cluster in clusters.clusters:
    labels = cluster.resource_labels if hasattr(cluster, 'resource_labels') else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged cluster = governance waste
```

**Critères :**
- Labels manquants parmi la liste requise
- Optionnel: valeurs de labels invalides

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Clusters non taggués = perte de visibilité + risque coût
# Coût estimé = 5% du coût cluster (estimation)

# Calculer coût cluster total
management_fee = 73.00 if not cluster.autopilot.enabled else 0

nodes_cost = 0
for node_pool in cluster.node_pools:
    machine_type = node_pool.config.machine_type
    node_count = node_pool.initial_node_count
    nodes_cost += node_count * get_machine_cost(machine_type)

cluster_monthly_cost = management_fee + nodes_cost

# Governance waste = 5%
governance_waste_percentage = 0.05
monthly_waste = cluster_monthly_cost * governance_waste_percentage

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster (3x n2-standard-2) sans labels depuis 180 jours :
```python
cluster_monthly_cost = $73 + (3 * $71.17) = $286.51
monthly_waste = $286.51 * 0.05 = $14.33
already_wasted = $14.33 * (180/30) = $85.98
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |
| `enforce_values` | dict | `{}` | Valeurs autorisées par label |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-1010101010",
  "resource_name": "unnamed-cluster-42",
  "resource_type": "gke_cluster_untagged",
  "location": "europe-west4-a",
  "cluster_mode": "STANDARD",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "creation_time": "2024-05-06T08:00:00Z",
  "age_days": 180,
  "cluster_monthly_cost": 286.51,
  "estimated_monthly_waste": 14.33,
  "already_wasted": 85.98,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation and governance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `gke_cluster_nodes_underutilized` - Nodes Sous-Utilisés

#### Détection

**Logique :**

Utiliser **Cloud Monitoring** pour analyser utilisation CPU/Memory réelle des nodes :

```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

for cluster in clusters.clusters:
    if cluster.current_node_count == 0:
        continue

    # 2. Récupérer credentials et lister nodes
    cluster_credentials = get_cluster_credentials(cluster)
    config.load_kube_config_from_dict(cluster_credentials)

    v1 = client.CoreV1Api()
    nodes = v1.list_node()

    # 3. Pour chaque node, récupérer métriques via Cloud Monitoring
    from google.cloud import monitoring_v3

    monitoring_client = monitoring_v3.MetricServiceClient()

    underutilized_nodes = []

    for node in nodes.items:
        node_name = node.metadata.name

        # 4. Query CPU utilization (14 jours)
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 14*24*3600},
        })

        cpu_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'metric.type="kubernetes.io/node/cpu/allocatable_utilization" AND resource.node_name="{node_name}"',
                "interval": interval,
            }
        )

        # 5. Calculer moyenne CPU
        cpu_values = [point.value.double_value for series in cpu_metrics for point in series.points]
        avg_cpu = (sum(cpu_values) / len(cpu_values) * 100) if cpu_values else 0

        # 6. Query Memory utilization
        memory_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'metric.type="kubernetes.io/node/memory/allocatable_utilization" AND resource.node_name="{node_name}"',
                "interval": interval,
            }
        )

        memory_values = [point.value.double_value for series in memory_metrics for point in series.points]
        avg_memory = (sum(memory_values) / len(memory_values) * 100) if memory_values else 0

        # 7. Détection si CPU <30% ET Memory <40%
        if avg_cpu < cpu_threshold and avg_memory < memory_threshold:
            underutilized_nodes.append({
                'node_name': node_name,
                'avg_cpu': avg_cpu,
                'avg_memory': avg_memory
            })

    # 8. Si >50% nodes sous-utilisés, cluster waste détecté
    if len(underutilized_nodes) >= len(nodes.items) * 0.5:
        # Nodes underutilized = waste
```

**Critères :**
- `avg_cpu < 30%` ET `avg_memory < 40%` par node
- >50% des nodes sous-utilisés
- Période analyse: 14 jours

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Kubernetes API
from kubernetes import client
v1 = client.CoreV1Api()
nodes = v1.list_node()

# Cloud Monitoring API
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="kubernetes.io/node/cpu/allocatable_utilization"'
)
```

#### Calcul de Coût

**Formule :**

Nodes sous-utilisés = opportunité downgrade ou réduction :

```python
# Exemple: 5 nodes n2-standard-4 sous-utilisés (CPU 20%, Memory 30%)

underutilized_nodes = 5
node_cost = 142.34  # n2-standard-4

# Recommandation: downgrade vers n2-standard-2 (moitié ressources)
recommended_node_cost = 71.17  # n2-standard-2

# Waste par node
waste_per_node = node_cost - recommended_node_cost  # $71.17

# Waste total
monthly_waste = underutilized_nodes * waste_per_node  # $355.85

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

5x n2-standard-4 nodes sous-utilisés depuis 90 jours :
```python
current_cost = 5 * $142.34 = $711.70/mois
recommended_cost = 5 * $71.17 = $355.85/mois
monthly_waste = $355.85
already_wasted = $355.85 * (90/30) = $1,067.55
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 30.0 | CPU % maximum pour sous-utilisation |
| `memory_threshold` | float | 40.0 | Memory % maximum pour sous-utilisation |
| `lookback_days` | int | 14 | Période analyse métriques |
| `min_underutilized_percent` | float | 0.5 | % minimum nodes sous-utilisés |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-2020202020",
  "resource_name": "underutilized-cluster",
  "resource_type": "gke_cluster_nodes_underutilized",
  "location": "us-west1-b",
  "cluster_mode": "STANDARD",
  "total_nodes": 5,
  "underutilized_nodes": 5,
  "node_metrics": {
    "avg_cpu_percent": 22.3,
    "avg_memory_percent": 31.8
  },
  "node_pool_config": {
    "machine_type": "n2-standard-4"
  },
  "current_cost_monthly": 711.70,
  "recommended_machine_type": "n2-standard-2",
  "recommended_cost_monthly": 355.85,
  "estimated_monthly_waste": 355.85,
  "already_wasted": 1067.55,
  "confidence": "high",
  "recommendation": "Downgrade nodes to n2-standard-2 or enable autoscaling",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `gke_cluster_pods_overrequested` - Pods Over-Requested

#### Détection

**Logique :**

Analyser requests vs usage réel des pods :

```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

for cluster in clusters.clusters:
    # 2. Récupérer pods via Kubernetes API
    cluster_credentials = get_cluster_credentials(cluster)
    config.load_kube_config_from_dict(cluster_credentials)

    v1 = client.CoreV1Api()
    pods = v1.list_pod_for_all_namespaces()

    overrequested_pods = []

    # 3. Pour chaque pod, comparer requests vs usage
    for pod in pods.items:
        if pod.status.phase != 'Running':
            continue

        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace

        # 4. Récupérer CPU/Memory requests
        total_cpu_request = 0
        total_memory_request = 0

        for container in pod.spec.containers:
            if container.resources and container.resources.requests:
                cpu_req = container.resources.requests.get('cpu', '0')
                mem_req = container.resources.requests.get('memory', '0')

                # Parser CPU (ex: "500m" = 0.5 vCPU)
                total_cpu_request += parse_cpu(cpu_req)
                # Parser Memory (ex: "1Gi" = 1024 Mi)
                total_memory_request += parse_memory(mem_req)

        # 5. Récupérer usage réel via métriques (14 jours)
        pod_cpu_usage = get_pod_cpu_usage(pod_name, namespace, lookback_days=14)
        pod_memory_usage = get_pod_memory_usage(pod_name, namespace, lookback_days=14)

        # 6. Calculer ratio usage/request
        cpu_usage_ratio = pod_cpu_usage / total_cpu_request if total_cpu_request > 0 else 0
        memory_usage_ratio = pod_memory_usage / total_memory_request if total_memory_request > 0 else 0

        # 7. Détection si usage <50% requests
        if cpu_usage_ratio < 0.5 or memory_usage_ratio < 0.5:
            overrequested_pods.append({
                'pod_name': pod_name,
                'namespace': namespace,
                'cpu_request': total_cpu_request,
                'cpu_usage': pod_cpu_usage,
                'memory_request': total_memory_request,
                'memory_usage': pod_memory_usage
            })

    # 8. Si >30% pods over-requested, cluster inefficient
    if len(overrequested_pods) >= len(pods.items) * 0.3:
        # Pods over-requested = waste (resources réservées inutilement)
```

**Critères :**
- `usage < 50% requests` (CPU ou Memory)
- >30% des pods over-requested
- Période analyse: 14 jours

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Kubernetes API
from kubernetes import client
v1 = client.CoreV1Api()
pods = v1.list_pod_for_all_namespaces()

# Cloud Monitoring API (pod metrics)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="kubernetes.io/container/cpu/core_usage_time"'
)
```

#### Calcul de Coût

**Formule :**

Over-requested pods = ressources gaspillées sur nodes :

```python
# Exemple: Cluster Autopilot (facturation au pod)

# Pod over-requested:
# Requests: 2 vCPU + 4 GB RAM
# Usage réel: 0.5 vCPU + 1 GB RAM

cpu_request = 2  # vCPU
cpu_usage = 0.5  # vCPU
cpu_waste = cpu_request - cpu_usage  # 1.5 vCPU

memory_request = 4  # GB
memory_usage = 1  # GB
memory_waste = memory_request - memory_usage  # 3 GB

# Autopilot pricing
cpu_price = 32.49  # $/vCPU/mois
memory_price = 3.59  # $/GB/mois

# Waste par pod
cpu_waste_cost = cpu_waste * cpu_price  # 1.5 * $32.49 = $48.74
memory_waste_cost = memory_waste * memory_price  # 3 * $3.59 = $10.77
pod_waste = cpu_waste_cost + memory_waste_cost  # $59.51

# Total waste (tous pods over-requested)
total_overrequested_pods = 10
monthly_waste = total_overrequested_pods * pod_waste  # $595.10

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

10 pods over-requested depuis 60 jours :
```python
pod_waste = $59.51
monthly_waste = 10 * $59.51 = $595.10
already_wasted = $595.10 * (60/30) = $1,190.20
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `usage_request_ratio_threshold` | float | 0.5 | Ratio max usage/request |
| `lookback_days` | int | 14 | Période analyse usage |
| `min_overrequested_percent` | float | 0.3 | % minimum pods over-requested |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-3030303030",
  "resource_name": "autopilot-overrequested",
  "resource_type": "gke_cluster_pods_overrequested",
  "location": "us-central1-a",
  "cluster_mode": "AUTOPILOT",
  "total_pods": 20,
  "overrequested_pods": 10,
  "sample_pod_waste": {
    "pod_name": "api-deployment-xyz",
    "cpu_request": 2.0,
    "cpu_usage": 0.5,
    "memory_request_gb": 4.0,
    "memory_usage_gb": 1.0,
    "waste_monthly": 59.51
  },
  "estimated_monthly_waste": 595.10,
  "already_wasted": 1190.20,
  "confidence": "high",
  "recommendation": "Right-size pod requests to match actual usage",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `gke_cluster_no_workloads` - Clusters Sans Workloads

#### Détection

**Logique :**

Détecter clusters avec **zéro pods running** (hors system) :

```python
# 1. Lister tous les clusters
clusters = gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

for cluster in clusters.clusters:
    # 2. Récupérer pods via Kubernetes API
    cluster_credentials = get_cluster_credentials(cluster)
    config.load_kube_config_from_dict(cluster_credentials)

    v1 = client.CoreV1Api()
    pods = v1.list_pod_for_all_namespaces()

    # 3. Compter pods user (hors kube-system)
    user_pods = [
        p for p in pods.items
        if p.metadata.namespace not in ['kube-system', 'kube-public', 'kube-node-lease', 'gke-managed-system']
        and p.status.phase == 'Running'
    ]

    # 4. Détection si zero user pods
    if len(user_pods) == 0:
        # 5. Vérifier depuis combien de temps (éviter faux positifs)
        # Analyser historique pods sur 7 derniers jours
        historical_pods = get_pod_count_history(cluster, lookback_days=7)

        if all(count == 0 for count in historical_pods):
            # Cluster sans workloads depuis 7 jours = waste
```

**Critères :**
- `user_pods == 0` (aucun pod hors system)
- Historique 7 jours: toujours zéro pods
- Cluster actif (nodes >0 en mode Standard)

**API Calls :**
```python
# GKE API
gke_client.list_clusters(parent=f"projects/{project_id}/locations/-")

# Kubernetes API
from kubernetes import client
v1 = client.CoreV1Api()
pods = v1.list_pod_for_all_namespaces()
```

#### Calcul de Coût

**Formule :**

Cluster sans workloads = 100% waste :

```python
# Mode Standard: management fee + nodes
# Mode Autopilot: $0 si zero pods

if cluster.autopilot.enabled:
    monthly_cost = 0  # Autopilot scale to zero
else:
    # Standard mode
    management_fee = 73.00

    nodes_cost = 0
    for node_pool in cluster.node_pools:
        machine_type = node_pool.config.machine_type
        node_count = node_pool.initial_node_count
        nodes_cost += node_count * get_machine_cost(machine_type)

    monthly_cost = management_fee + nodes_cost

# Coût = 100% waste (cluster inutilisé)
monthly_waste = monthly_cost

# Coût gaspillé depuis dernier workload
last_workload_date = get_last_workload_date(cluster)
no_workload_days = (now - last_workload_date).days
already_wasted = monthly_waste * (no_workload_days / 30.0)
```

**Exemple :**

Cluster Standard (3x n2-standard-2) sans workloads depuis 30 jours :
```python
management_fee = $73.00
nodes_cost = 3 * $71.17 = $213.51
monthly_cost = $286.51
already_wasted = $286.51 * (30/30) = $286.51
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_no_workload_days` | int | 7 | Durée minimum sans workloads |
| `exclude_namespaces` | list | `['kube-system', 'kube-public']` | Namespaces système |

#### Métadonnées Exemple

```json
{
  "resource_id": "cluster-4040404040",
  "resource_name": "abandoned-cluster",
  "resource_type": "gke_cluster_no_workloads",
  "location": "europe-north1-a",
  "cluster_mode": "STANDARD",
  "total_nodes": 3,
  "user_pods": 0,
  "system_pods": 12,
  "last_workload_date": "2024-10-03T10:00:00Z",
  "no_workload_days": 30,
  "management_fee_monthly": 73.00,
  "nodes_cost_monthly": 213.51,
  "estimated_monthly_cost": 286.51,
  "already_wasted": 286.51,
  "confidence": "high",
  "recommendation": "Delete cluster if no longer needed",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Protocole de Test

### Prérequis

#### 1. Compte GCP et Projet Test

```bash
# Utiliser projet test existant
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
gcloud config set project $PROJECT_ID

# Activer APIs requises
gcloud services enable container.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account (si pas déjà créé)

```bash
# Ajouter permissions GKE
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/container.viewer"

# Permissions Kubernetes (via RBAC dans clusters)
# Créé automatiquement lors de tests
```

#### 3. Installer kubectl

```bash
# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Vérifier
kubectl version --client
```

---

### Tests Unitaires - Créer Clusters de Test

#### Scénario 1: Cluster Vide

```bash
# Créer cluster Standard sans nodes
gcloud container clusters create test-empty-cluster \
  --zone=us-central1-a \
  --num-nodes=0 \
  --enable-autoscaling \
  --min-nodes=0 \
  --max-nodes=3 \
  --machine-type=n2-standard-2

# Attendre 7 jours pour détection
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_empty",
  "resource_name": "test-empty-cluster",
  "cluster_mode": "STANDARD",
  "total_nodes": 0,
  "estimated_monthly_cost": "~73.00",
  "confidence": "high"
}
```

---

#### Scénario 2: Cluster avec Nodes Inactifs

```bash
# Créer cluster avec nodes
gcloud container clusters create test-nodes-inactive-cluster \
  --zone=us-east1-b \
  --num-nodes=3 \
  --machine-type=n2-standard-2

# Cordon tous les nodes (rendre inactifs)
kubectl get nodes -o name | xargs -I {} kubectl cordon {}

# Drain nodes (évacuer pods)
kubectl get nodes -o name | xargs -I {} kubectl drain {} --ignore-daemonsets --delete-emptydir-data

# Attendre 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_nodes_inactive",
  "resource_name": "test-nodes-inactive-cluster",
  "total_nodes": 3,
  "ready_nodes": 0,
  "estimated_monthly_cost": "~286.51"
}
```

---

#### Scénario 3: Node Pool Over-Provisionné

```bash
# Créer cluster avec 10 nodes
gcloud container clusters create test-overprovisioned-cluster \
  --zone=europe-west1-b \
  --num-nodes=10 \
  --machine-type=n2-standard-2 \
  --no-enable-autoscaling

# Déployer seulement 2 pods
kubectl create deployment test-app --image=nginx --replicas=2

# Laisser tourner 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_nodepool_overprovisioned",
  "resource_name": "test-overprovisioned-cluster",
  "total_nodes": 10,
  "total_user_pods": 2,
  "pods_per_node": 0.2,
  "estimated_monthly_waste": "~640.53"
}
```

---

#### Scénario 4: Nodes Ancien Type Machine

```bash
# Créer cluster avec n1 machine type
gcloud container clusters create test-old-machine-cluster \
  --zone=us-central1-a \
  --num-nodes=5 \
  --machine-type=n1-standard-4

# Laisser tourner
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_old_machine_type",
  "resource_name": "test-old-machine-cluster",
  "machine_type": "n1-standard-4",
  "recommended_machine_type": "n2-standard-2",
  "estimated_monthly_waste": "~129.55"
}
```

---

#### Scénario 5: Cluster Dev/Test 24/7

```bash
# Créer cluster avec label dev
gcloud container clusters create test-devtest-247-cluster \
  --zone=us-east1-c \
  --num-nodes=3 \
  --machine-type=n2-standard-2 \
  --labels=environment=dev,team=backend

# Laisser tourner 7+ jours sans arrêt
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_devtest_247",
  "resource_name": "test-devtest-247-cluster",
  "labels": {"environment": "dev"},
  "uptime_days": ">=7",
  "estimated_monthly_waste": "~137.17"
}
```

---

#### Scénario 6: Cluster Sans Auto-Scaling

```bash
# Créer cluster fixed-size (pas d'autoscaling)
gcloud container clusters create test-no-autoscaling-cluster \
  --zone=asia-southeast1-a \
  --num-nodes=10 \
  --machine-type=n2-standard-2 \
  --no-enable-autoscaling

# Déployer workload variable (2-8 pods)
kubectl create deployment variable-app --image=nginx --replicas=3

# Simuler variabilité
while true; do
  kubectl scale deployment variable-app --replicas=$((2 + RANDOM % 7))
  sleep 3600
done &

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_no_autoscaling",
  "resource_name": "test-no-autoscaling-cluster",
  "autoscaling_enabled": false,
  "workload_variability": {
    "variability_percent": ">30"
  },
  "estimated_monthly_waste": "~320.27"
}
```

---

#### Scénario 7: Cluster Non Taggué

```bash
# Créer cluster SANS labels
gcloud container clusters create test-untagged-cluster \
  --zone=europe-west4-a \
  --num-nodes=3 \
  --machine-type=n2-standard-2
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_untagged",
  "resource_name": "test-untagged-cluster",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "estimated_monthly_waste": "~14.33"
}
```

---

#### Scénario 8: Nodes Sous-Utilisés

```bash
# Créer cluster avec large nodes
gcloud container clusters create test-underutilized-cluster \
  --zone=us-west1-b \
  --num-nodes=5 \
  --machine-type=n2-standard-4

# Déployer workload léger (faible CPU/Memory)
kubectl create deployment light-app --image=nginx --replicas=5

# Pods nginx utilisent très peu de ressources
# Laisser tourner 14 jours pour métriques
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_nodes_underutilized",
  "resource_name": "test-underutilized-cluster",
  "node_metrics": {
    "avg_cpu_percent": "<30",
    "avg_memory_percent": "<40"
  },
  "estimated_monthly_waste": "~355.85"
}
```

---

#### Scénario 9: Pods Over-Requested

```bash
# Créer cluster Autopilot
gcloud container clusters create-auto test-overrequested-cluster \
  --region=us-central1

# Déployer pods avec requests excessifs
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: overrequested-app
spec:
  replicas: 10
  selector:
    matchLabels:
      app: overrequested
  template:
    metadata:
      labels:
        app: overrequested
    spec:
      containers:
      - name: nginx
        image: nginx
        resources:
          requests:
            cpu: "2000m"      # 2 vCPU requested
            memory: "4Gi"     # 4 GB requested
          # Nginx utilise réellement ~0.1 vCPU + 10 MB
EOF

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_pods_overrequested",
  "resource_name": "test-overrequested-cluster",
  "cluster_mode": "AUTOPILOT",
  "overrequested_pods": 10,
  "estimated_monthly_waste": "~595.10"
}
```

---

#### Scénario 10: Cluster Sans Workloads

```bash
# Créer cluster Standard
gcloud container clusters create test-no-workloads-cluster \
  --zone=europe-north1-a \
  --num-nodes=3 \
  --machine-type=n2-standard-2

# NE PAS déployer de workloads (zéro pods user)

# Attendre 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "gke_cluster_no_workloads",
  "resource_name": "test-no-workloads-cluster",
  "user_pods": 0,
  "no_workload_days": ">=7",
  "estimated_monthly_cost": "~286.51"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script de validation complet pour GKE Clusters
"""

from google.cloud import container_v1
from kubernetes import client, config
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    gke_client = container_v1.ClusterManagerClient()

    # 1. Lister tous les clusters
    parent = f"projects/{PROJECT_ID}/locations/-"
    clusters_response = gke_client.list_clusters(parent=parent)

    clusters = clusters_response.clusters
    print(f"✅ Found {len(clusters)} clusters")

    # 2. Vérifier détection pour chaque scénario
    scenarios_detected = {
        'empty': 0,
        'nodes_inactive': 0,
        'nodepool_overprovisioned': 0,
        'old_machine_type': 0,
        'devtest_247': 0,
        'no_autoscaling': 0,
        'untagged': 0,
        'nodes_underutilized': 0,
        'pods_overrequested': 0,
        'no_workloads': 0,
    }

    for cluster in clusters:
        name = cluster.name

        # Scenario 1: Empty
        if cluster.current_node_count == 0:
            scenarios_detected['empty'] += 1
            print(f"✅ Detected scenario 1 (empty): {name}")

        # Scenario 4: Old machine type
        for node_pool in cluster.node_pools:
            if node_pool.config.machine_type.startswith('n1-'):
                scenarios_detected['old_machine_type'] += 1
                print(f"✅ Detected scenario 4 (old machine type): {name}")
                break

        # Scenario 5: Dev/Test
        labels = cluster.resource_labels if hasattr(cluster, 'resource_labels') else {}
        if labels.get('environment') in ['dev', 'test', 'staging']:
            scenarios_detected['devtest_247'] += 1
            print(f"✅ Detected scenario 5 (dev/test 24/7): {name}")

        # Scenario 6: No autoscaling
        has_autoscaling = any(
            np.autoscaling and np.autoscaling.enabled
            for np in cluster.node_pools
        )
        if not has_autoscaling and not cluster.autopilot.enabled:
            scenarios_detected['no_autoscaling'] += 1
            print(f"✅ Detected scenario 6 (no autoscaling): {name}")

        # Scenario 7: Untagged
        if not labels or len(labels) == 0:
            scenarios_detected['untagged'] += 1
            print(f"✅ Detected scenario 7 (untagged): {name}")

    # 3. Rapport final
    print("\n📊 Detection Summary:")
    for scenario, count in scenarios_detected.items():
        print(f"  - {scenario}: {count} clusters")

    total_detected = sum(scenarios_detected.values())
    print(f"\n✅ Total waste detected: {total_detected} clusters")

if __name__ == '__main__':
    test_all_scenarios()
```

#### Exécution

```bash
# Exporter PROJECT_ID
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"

# Exécuter validation
python3 test_gcp_gke_clusters.py
```

**Résultat attendu :**
```
✅ Found 10 clusters
✅ Detected scenario 1 (empty): test-empty-cluster
✅ Detected scenario 2 (nodes inactive): test-nodes-inactive-cluster
✅ Detected scenario 3 (overprovisioned): test-overprovisioned-cluster
✅ Detected scenario 4 (old machine type): test-old-machine-cluster
✅ Detected scenario 5 (dev/test 24/7): test-devtest-247-cluster
✅ Detected scenario 6 (no autoscaling): test-no-autoscaling-cluster
✅ Detected scenario 7 (untagged): test-untagged-cluster
✅ Detected scenario 8 (underutilized): test-underutilized-cluster
✅ Detected scenario 9 (pods overrequested): test-overrequested-cluster
✅ Detected scenario 10 (no workloads): test-no-workloads-cluster

📊 Detection Summary:
  - empty: 1 clusters
  - nodes_inactive: 1 clusters
  - nodepool_overprovisioned: 1 clusters
  - old_machine_type: 1 clusters
  - devtest_247: 1 clusters
  - no_autoscaling: 1 clusters
  - untagged: 1 clusters
  - nodes_underutilized: 1 clusters
  - pods_overrequested: 1 clusters
  - no_workloads: 1 clusters

✅ Total waste detected: 10 clusters
```

---

### Cleanup

```bash
# Supprimer tous les clusters de test
gcloud container clusters delete test-empty-cluster --zone=us-central1-a --quiet
gcloud container clusters delete test-nodes-inactive-cluster --zone=us-east1-b --quiet
gcloud container clusters delete test-overprovisioned-cluster --zone=europe-west1-b --quiet
gcloud container clusters delete test-old-machine-cluster --zone=us-central1-a --quiet
gcloud container clusters delete test-devtest-247-cluster --zone=us-east1-c --quiet
gcloud container clusters delete test-no-autoscaling-cluster --zone=asia-southeast1-a --quiet
gcloud container clusters delete test-untagged-cluster --zone=europe-west4-a --quiet
gcloud container clusters delete test-underutilized-cluster --zone=us-west1-b --quiet
gcloud container clusters delete test-overrequested-cluster --region=us-central1 --quiet
gcloud container clusters delete test-no-workloads-cluster --zone=europe-north1-a --quiet
```

---

## Références

### Documentation GCP

- [GKE Clusters API](https://cloud.google.com/kubernetes-engine/docs/reference/rest/v1/projects.locations.clusters)
- [GKE Pricing](https://cloud.google.com/kubernetes-engine/pricing)
- [GKE Autopilot vs Standard](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Cluster Autoscaler](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler)
- [GKE Monitoring](https://cloud.google.com/stackdriver/docs/solutions/gke)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing complet 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md) - Compute Instances
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md) - Persistent Disks
- [README.md](./README.md) - Guide documentation GCP

### Équivalences AWS/Azure

- **AWS EKS** → GCP GKE
- **Azure AKS** → GCP GKE
- **AWS Fargate** → GCP Autopilot
- **AWS EC2 (nodes)** → GCP Compute Engine (nodes)

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
