# CloudWaste - Couverture 100% GCP Cloud Bigtable

**Resource Type:** `Database : Cloud Bigtable`
**Provider:** Google Cloud Platform (GCP)
**API:** `bigtableadmin.googleapis.com` (Bigtable Admin API v2)
**Équivalents:** AWS DynamoDB, Azure Cosmos DB (Cassandra API), Apache HBase
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing Cloud Bigtable](#modèle-de-pricing-cloud-bigtable)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Instances Sous-Utilisées](#1-bigtable_underutilized---instances-sous-utilisées)
  - [2. Multi-Cluster Inutile](#2-bigtable_unnecessary_multicluster---multi-cluster-inutile)
  - [3. SSD Storage Inutile](#3-bigtable_unnecessary_ssd---ssd-storage-inutile)
  - [4. Instances Dev/Test Over-Provisioned](#4-bigtable_devtest_overprovisioned---instances-devtest-over-provisioned)
  - [5. Instances Idle](#5-bigtable_idle---instances-idle)
  - [6. Instances avec Tables Vides](#6-bigtable_empty_tables---instances-avec-tables-vides)
  - [7. Instances Non Taguées](#7-bigtable_untagged---instances-non-taguées)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Nodes avec CPU Faible](#8-bigtable_low_cpu---nodes-avec-cpu-faible)
  - [9. Storage Type Suboptimal](#9-bigtable_storage_type_suboptimal---storage-type-suboptimal)
  - [10. Tables avec Zero Reads](#10-bigtable_zero_read_tables---tables-avec-zero-reads)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte Cloud Bigtable

**Cloud Bigtable** est la base de données **NoSQL wide-column** de GCP, offrant :

- **Wide-column store** (modèle HBase/Cassandra)
- **Pétabyte scale** (jusqu'à pétabytes de données)
- **Faible latence** (<10ms read/write)
- **High throughput** (millions ops/sec)
- **Use cases** : Time-series, IoT, analytics, AdTech, FinTech

### Architecture Bigtable

```
Instance Bigtable
├── Cluster 1 (zone-a)
│   ├── Node 1 (SSD ou HDD)
│   ├── Node 2
│   └── Node N
├── Cluster 2 (zone-b) - Optional replication
│   └── Nodes...
└── Tables
    ├── Table 1
    │   └── Column families
    └── Table N
```

### Caractéristiques Principales

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Nodes** | Unités compute (1-1000 nodes/cluster) | $226-474/node/mois |
| **Storage Type** | SSD (performance) ou HDD (économique) | SSD = 2.1x nodes, 6.5x storage |
| **Clusters** | Single ou Multi-cluster (replication) | Multi = 2x+ coût |
| **Scaling** | Manual ou Autoscaling | Autoscaling évite over-provisioning |
| **Replication** | Multi-cluster automatic | +100% nodes cost |

### Storage Types

| Type | Node Price | Storage Price | Throughput | Use Case |
|------|-----------|---------------|-----------|----------|
| **SSD** | $0.65/hour/node<br>~$474/node/mois | $0.17/GB/mois | 10K reads/sec/node<br>10K writes/sec/node | Haute performance, faible latence |
| **HDD** | $0.31/hour/node<br>~$226/node/mois | $0.026/GB/mois | 500 reads/sec/node<br>500 writes/sec/node | Données froides, archivage, batch |

**Ratio coûts :**
- SSD nodes : 2.1x plus cher que HDD nodes
- SSD storage : 6.5x plus cher que HDD storage

### Waste Typique

1. **SSD au lieu de HDD** : 6.5x surcoût storage pour cold data ($170 vs $26 pour 1 TB)
2. **Multi-cluster inutile** : +100% nodes cost pour dev/test
3. **Nodes over-provisioned** : 10 nodes pour 1000 ops/sec = surcoût
4. **Dev/test avec production nodes** : $474/node/mois pour environnement non-prod
5. **Instances idle** : Zero requests mais nodes actifs
6. **Tables vides** : Instance sans données
7. **Pas d'autoscaling** : Nodes fixes alors que charge varie

---

## Modèle de Pricing Cloud Bigtable

### Nodes Pricing (par mois)

| Configuration | Nodes | SSD | HDD | Différence |
|--------------|-------|-----|-----|-----------|
| **Dev minimal** | 1 | $474 | $226 | -52% |
| **Small prod** | 3 | $1,422 | $678 | -52% |
| **Medium prod** | 6 | $2,844 | $1,356 | -52% |
| **Large prod** | 10 | $4,740 | $2,260 | -52% |
| **X-Large** | 20 | $9,480 | $4,520 | -52% |

**Formules :**
- **SSD node :** $0.65/hour = $474/mois
- **HDD node :** $0.31/hour = $226/mois

### Storage Pricing

| Type | Prix/GB/Mois | Exemple 1 TB | Exemple 10 TB |
|------|-------------|--------------|---------------|
| **SSD** | $0.17 | $170 | $1,700 |
| **HDD** | $0.026 | $26 | $260 |
| **Ratio** | 6.5x | 6.5x | 6.5x |

### Backup Pricing

- **Backups :** $0.10/GB/mois (identique SSD/HDD)

### Network Pricing

- **Ingress :** Gratuit
- **Egress (internet) :** $0.12/GB (après 1 GB gratuit)
- **Egress (intra-région) :** Gratuit

### Exemples Coûts Mensuels

#### Scénario 1 : Dev/Test Minimal (SSD)

```
Config: 1 node SSD, 100 GB storage
─────────────────────────────
Nodes: 1 × $474 = $474
Storage: 100 GB × $0.17 = $17
Backups: 150 GB × $0.10 = $15
─────────────────────────────
TOTAL: $506/mois
```

#### Scénario 2 : Production Regional (SSD, 3 nodes)

```
Config: 3 nodes SSD, 2 TB storage, 1 cluster
─────────────────────────────
Nodes: 3 × $474 = $1,422
Storage: 2000 GB × $0.17 = $340
Backups: 3000 GB × $0.10 = $300
─────────────────────────────
TOTAL: $2,062/mois
```

#### Scénario 3 : Production Multi-Cluster (SSD, 2 clusters × 3 nodes)

```
Config: 6 nodes total (2 clusters × 3 nodes), 2 TB storage
─────────────────────────────
Nodes: 6 × $474 = $2,844
Storage: 2000 GB × $0.17 = $340 (répliqué automatiquement)
Backups: 3000 GB × $0.10 = $300
─────────────────────────────
TOTAL: $3,484/mois
```

#### Scénario 4 : Archivage HDD (10 TB cold data)

```
Config: 3 nodes HDD, 10 TB storage
─────────────────────────────
Nodes: 3 × $226 = $678
Storage: 10000 GB × $0.026 = $260
Backups: 15000 GB × $0.10 = $1,500
─────────────────────────────
TOTAL: $2,438/mois
```

**Comparaison SSD vs HDD (10 TB) :**
- SSD : $1,422 + $1,700 = $3,122/mois
- HDD : $678 + $260 = $938/mois
- **Économie HDD : -70% ($2,184/mois)**

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `bigtable_underutilized` - Instances Sous-Utilisées

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances Bigtable
from google.cloud import bigtable_admin_v2

bigtable_admin_client = bigtable_admin_v2.BigtableInstanceAdminClient()

parent = f"projects/{project_id}"
instances = bigtable_admin_client.list_instances(parent=parent)

# 2. Pour chaque instance, récupérer clusters
for instance in instances.instances:
    instance_name = instance.name

    # 3. Pour chaque cluster, récupérer node count
    clusters = bigtable_admin_client.list_clusters(parent=instance_name)

    for cluster in clusters.clusters:
        cluster_id = cluster.name.split('/')[-1]
        node_count = cluster.serve_nodes
        storage_type = cluster.default_storage_type  # SSD ou HDD

        # 4. Récupérer métriques CPU (14 jours)
        from google.cloud import monitoring_v3

        monitoring_client = monitoring_v3.MetricServiceClient()

        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 14*24*3600},
        })

        # Métrique: bigtable.googleapis.com/cluster/cpu_load
        cpu_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="bigtable_cluster" AND resource.cluster="{cluster_id}" AND metric.type="bigtable.googleapis.com/cluster/cpu_load"',
                "interval": interval,
            }
        )

        # 5. Calculer CPU moyen
        cpu_values = [
            point.value.double_value
            for series in cpu_metrics
            for point in series.points
        ]

        avg_cpu = (sum(cpu_values) / len(cpu_values) * 100) if cpu_values else 0

        # 6. Bigtable optimal CPU: 70% (Google recommendation)
        # Si avg_cpu < 30%, under-utilized

        if avg_cpu < cpu_threshold:
            # Calculer nodes recommandés
            # Formule: nodes_optimal = nodes_actuel * (avg_cpu / 70)
            optimal_nodes = max(1, int(node_count * (avg_cpu / 70.0)))

            if optimal_nodes < node_count:
                # Cluster sous-utilisé = waste détecté
```

**Critères :**
- `avg_cpu < 30%` sur 14 jours
- Nodes recommandés < Nodes actuels
- Cluster actif (state = READY)

**API Calls :**
```python
# Bigtable Admin API
from google.cloud import bigtable_admin_v2

bigtable_admin_client = bigtable_admin_v2.BigtableInstanceAdminClient()
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
clusters = bigtable_admin_client.list_clusters(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/cluster/cpu_load"'
)
```

#### Calcul de Coût

**Formule :**

Under-utilization = différence nodes actuels vs recommandés :

```python
# Exemple: 6 nodes SSD avec CPU 20%

current_nodes = 6
avg_cpu = 20.0
storage_type = 'SSD'

# Nodes optimal pour CPU 70%
optimal_nodes = max(1, int(6 * (20.0 / 70.0)))  # 2 nodes
optimal_nodes = 2

# Node pricing
if storage_type == 'SSD':
    cost_per_node = 474  # $/mois
else:
    cost_per_node = 226  # $/mois

# Coût actuel
current_cost = current_nodes * cost_per_node  # 6 × $474 = $2,844

# Coût optimal
optimal_cost = optimal_nodes * cost_per_node  # 2 × $474 = $948

# Waste
monthly_waste = current_cost - optimal_cost  # $1,896

# Storage et backups identiques (pas de waste)

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster 6 nodes SSD avec CPU 20% depuis 90 jours :
```python
current_cost = 6 * $474 = $2,844/mois
optimal_cost = 2 * $474 = $948/mois
monthly_waste = $1,896
already_wasted = $1,896 * (90/30) = $5,688
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 30.0 | CPU % maximum pour sous-utilisation |
| `target_cpu` | float | 70.0 | CPU optimal Bigtable (Google recommendation) |
| `lookback_days` | int | 14 | Période analyse métriques |
| `min_savings_threshold` | float | 100.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1234567890",
  "resource_name": "prod-bigtable-instance",
  "resource_type": "bigtable_underutilized",
  "cluster_id": "cluster-us-central1",
  "location": "us-central1-a",
  "state": "READY",
  "storage_type": "SSD",
  "current_node_count": 6,
  "cpu_metrics": {
    "avg_cpu_14d": 22.1,
    "max_cpu_14d": 41.5
  },
  "recommended_node_count": 2,
  "current_cost_monthly": 2844.00,
  "recommended_cost_monthly": 948.00,
  "estimated_monthly_waste": 1896.00,
  "already_wasted": 5688.00,
  "confidence": "high",
  "recommendation": "Reduce from 6 nodes to 2 nodes (67% cost savings)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `bigtable_unnecessary_multicluster` - Multi-Cluster Inutile

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, compter clusters
for instance in instances.instances:
    instance_name = instance.name

    # 3. Lister clusters
    clusters_response = bigtable_admin_client.list_clusters(parent=instance_name)
    clusters_list = list(clusters_response.clusters)

    # 4. Détection si multi-cluster (≥2 clusters)
    if len(clusters_list) >= 2:
        # 5. Vérifier labels (dev/test ne nécessite pas replication)
        labels = instance.labels if hasattr(instance, 'labels') else {}
        environment = labels.get('environment', '').lower()

        if environment in ['dev', 'test', 'staging', 'development']:
            # Multi-cluster pour dev/test = waste évident
            # Économie: -50%+ coût nodes

            # Calculer waste
            total_nodes = sum([c.serve_nodes for c in clusters_list])
            primary_cluster_nodes = clusters_list[0].serve_nodes

            # Nodes inutiles (replicas)
            wasted_nodes = total_nodes - primary_cluster_nodes

            storage_type = clusters_list[0].default_storage_type

            # Multi-cluster inutile = waste détecté
```

**Critères :**
- Nombre clusters ≥ 2 (multi-cluster/replication)
- Labels `environment in ['dev', 'test', 'staging']` OU
- Pas de workload multi-régional nécessitant replication

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
bigtable_admin_client.list_clusters(parent=instance_name)
```

#### Calcul de Coût

**Formule :**

Multi-cluster → Single cluster = -50%+ coût nodes :

```python
# Exemple: 2 clusters × 3 nodes SSD pour dev

clusters = 2
nodes_per_cluster = 3
total_nodes = 6

storage_type = 'SSD'
cost_per_node = 474  # $/mois

# Coût actuel (multi-cluster)
current_cost = total_nodes * cost_per_node  # 6 × $474 = $2,844

# Coût optimal (single cluster)
recommended_nodes = nodes_per_cluster  # 3 nodes
recommended_cost = recommended_nodes * cost_per_node  # 3 × $474 = $1,422

# Waste = coût replica
monthly_waste = current_cost - recommended_cost  # $1,422

# Storage répliqué automatiquement (pas de surcoût storage)
# Backups identiques

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance dev avec 2 clusters × 3 nodes SSD depuis 120 jours :
```python
current_cost = 6 * $474 = $2,844/mois
recommended_cost = 3 * $474 = $1,422/mois
monthly_waste = $1,422
already_wasted = $1,422 * (120/30) = $5,688
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `min_savings_threshold` | float | 200.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-9876543210",
  "resource_name": "dev-bigtable-multicluster",
  "resource_type": "bigtable_unnecessary_multicluster",
  "state": "READY",
  "labels": {
    "environment": "dev",
    "team": "backend"
  },
  "clusters": [
    {
      "cluster_id": "cluster-us-central1",
      "location": "us-central1-a",
      "node_count": 3,
      "storage_type": "SSD"
    },
    {
      "cluster_id": "cluster-us-east1",
      "location": "us-east1-b",
      "node_count": 3,
      "storage_type": "SSD"
    }
  ],
  "total_nodes": 6,
  "current_cost_monthly": 2844.00,
  "recommended_clusters": 1,
  "recommended_nodes": 3,
  "recommended_cost_monthly": 1422.00,
  "estimated_monthly_waste": 1422.00,
  "already_wasted": 5688.00,
  "savings_percentage": 50,
  "confidence": "high",
  "recommendation": "Remove replica cluster - dev environment doesn't need replication",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `bigtable_unnecessary_ssd` - SSD Storage Inutile

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, vérifier storage type
for instance in instances.instances:
    instance_name = instance.name

    # 3. Lister clusters
    clusters = bigtable_admin_client.list_clusters(parent=instance_name)

    for cluster in clusters.clusters:
        storage_type = cluster.default_storage_type  # SSD ou HDD

        # 4. Si SSD, analyser pattern d'accès
        if storage_type == bigtable_admin_v2.StorageType.SSD:
            cluster_id = cluster.name.split('/')[-1]

            # 5. Récupérer métriques read latency et throughput
            # Si données accédées rarement (<100 reads/sec), HDD suffit

            from google.cloud import monitoring_v3

            monitoring_client = monitoring_v3.MetricServiceClient()

            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(time.time())},
                "start_time": {"seconds": int(time.time()) - 14*24*3600},
            })

            # Métrique: bigtable.googleapis.com/server/request_count
            read_metrics = monitoring_client.list_time_series(
                request={
                    "name": f"projects/{project_id}",
                    "filter": f'resource.type="bigtable_cluster" AND resource.cluster="{cluster_id}" AND metric.type="bigtable.googleapis.com/server/request_count" AND metric.label.method="Bigtable.ReadRows"',
                    "interval": interval,
                }
            )

            # Calculer read ops/sec moyen
            read_counts = [
                point.value.int64_value
                for series in read_metrics
                for point in series.points
            ]

            if read_counts:
                total_reads = sum(read_counts)
                avg_reads_per_sec = total_reads / (14 * 24 * 3600)

                # 6. HDD supporte 500 reads/sec/node
                # Si avg_reads < 100/sec/node, HDD suffit

                node_count = cluster.serve_nodes
                reads_per_node = avg_reads_per_sec / node_count if node_count > 0 else 0

                if reads_per_node < hdd_threshold_reads_per_node:
                    # SSD inutile, HDD suffit
                    # Économie: -52% nodes, -85% storage
```

**Critères :**
- `storage_type == 'SSD'`
- `avg_reads_per_sec_per_node < 100` (HDD supporte 500 reads/sec/node)
- Pattern d'accès compatible HDD (données froides)

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
bigtable_admin_client.list_clusters(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/server/request_count"'
)
```

#### Calcul de Coût

**Formule :**

SSD → HDD = -52% nodes, -85% storage :

```python
# Exemple: 3 nodes SSD, 5 TB storage, low reads

node_count = 3
storage_size_gb = 5000

# Coût actuel (SSD)
ssd_nodes_cost = 3 * 474 = $1,422/mois
ssd_storage_cost = 5000 * 0.17 = $850/mois
ssd_total = $2,272/mois

# Coût recommandé (HDD)
hdd_nodes_cost = 3 * 226 = $678/mois
hdd_storage_cost = 5000 * 0.026 = $130/mois
hdd_total = $808/mois

# Waste = différence
monthly_waste = ssd_total - hdd_total  # $1,464

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster 3 nodes SSD avec 5 TB storage (low reads) depuis 180 jours :
```python
ssd_cost = $2,272/mois
hdd_cost = $808/mois
monthly_waste = $1,464
already_wasted = $1,464 * (180/30) = $8,784
savings_percentage = 64.4%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `hdd_threshold_reads_per_node` | float | 100.0 | Reads/sec/node max pour HDD |
| `lookback_days` | int | 14 | Période analyse accès |
| `min_savings_threshold` | float | 200.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-5555555555",
  "resource_name": "archive-bigtable-ssd",
  "resource_type": "bigtable_unnecessary_ssd",
  "cluster_id": "cluster-us-west1",
  "location": "us-west1-a",
  "state": "READY",
  "storage_type": "SSD",
  "node_count": 3,
  "storage_size_gb": 5000,
  "read_metrics": {
    "avg_reads_per_sec": 180,
    "avg_reads_per_sec_per_node": 60
  },
  "current_cost_monthly": 2272.00,
  "recommended_storage_type": "HDD",
  "recommended_cost_monthly": 808.00,
  "estimated_monthly_waste": 1464.00,
  "already_wasted": 8784.00,
  "savings_percentage": 64.4,
  "confidence": "high",
  "recommendation": "Migrate to HDD storage - low read throughput (60 reads/sec/node)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `bigtable_devtest_overprovisioned` - Instances Dev/Test Over-Provisioned

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, vérifier labels
for instance in instances.instances:
    labels = instance.labels if hasattr(instance, 'labels') else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment = dev/test
    if environment in ['dev', 'test', 'staging', 'development']:
        # 4. Vérifier config clusters
        clusters = bigtable_admin_client.list_clusters(parent=instance.name)

        for cluster in clusters.clusters:
            node_count = cluster.serve_nodes
            storage_type = cluster.default_storage_type

            # 5. Dev/test devrait utiliser minimum nodes (1 node)
            # Et préférablement HDD (pas SSD)

            if node_count >= devtest_node_threshold or storage_type == bigtable_admin_v2.StorageType.SSD:
                # Dev/test over-provisioned = waste

                # Recommandation: 1 node HDD pour dev/test
                recommended_nodes = 1
                recommended_storage_type = 'HDD'

                # Calculer économie
```

**Critères :**
- `labels.environment in ['dev', 'test', 'staging']`
- `node_count >= 3` (production config) OU
- `storage_type == 'SSD'` (HDD recommandé pour dev/test)

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
bigtable_admin_client.list_clusters(parent=instance_name)
```

#### Calcul de Coût

**Formule :**

Dev/test avec production config = surcoût :

```python
# Exemple: Dev instance avec 3 nodes SSD

current_nodes = 3
current_storage_type = 'SSD'

# Coût actuel (dev avec config prod)
current_cost = 3 * 474 = $1,422/mois

# Recommandation dev/test: 1 node HDD
recommended_nodes = 1
recommended_cost = 1 * 226 = $226/mois

# Waste
monthly_waste = $1,422 - $226 = $1,196

# Storage identique (minimal pour dev)

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance dev 3 nodes SSD depuis 90 jours :
```python
current_cost = $1,422/mois
recommended_cost = $226/mois (1 node HDD)
monthly_waste = $1,196
already_wasted = $1,196 * (90/30) = $3,588
savings_percentage = 84%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `devtest_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `devtest_node_threshold` | int | 3 | Nodes max recommandé pour dev/test |
| `recommended_devtest_nodes` | int | 1 | Nodes optimal dev/test |
| `recommended_devtest_storage` | str | `'HDD'` | Storage type optimal dev/test |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-7777777777",
  "resource_name": "dev-bigtable-large",
  "resource_type": "bigtable_devtest_overprovisioned",
  "cluster_id": "cluster-us-central1",
  "location": "us-central1-a",
  "state": "READY",
  "labels": {
    "environment": "dev",
    "team": "data"
  },
  "storage_type": "SSD",
  "node_count": 3,
  "current_cost_monthly": 1422.00,
  "recommended_node_count": 1,
  "recommended_storage_type": "HDD",
  "recommended_cost_monthly": 226.00,
  "estimated_monthly_waste": 1196.00,
  "already_wasted": 3588.00,
  "savings_percentage": 84,
  "confidence": "high",
  "recommendation": "Reduce to 1 node HDD for dev/test environment",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `bigtable_idle` - Instances Idle

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, récupérer métriques requests (14 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances.instances:
    instance_id = instance.name.split('/')[-1]

    # 3. Lister clusters
    clusters = bigtable_admin_client.list_clusters(parent=instance.name)

    for cluster in clusters.clusters:
        cluster_id = cluster.name.split('/')[-1]

        # 4. Query request count (read + write)
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 14*24*3600},
        })

        request_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="bigtable_cluster" AND resource.cluster="{cluster_id}" AND metric.type="bigtable.googleapis.com/server/request_count"',
                "interval": interval,
            }
        )

        # 5. Calculer total requests
        total_requests = sum([
            point.value.int64_value
            for series in request_metrics
            for point in series.points
        ])

        # 6. Détection si zero requests
        if total_requests == 0:
            # Cluster idle = 100% waste
```

**Critères :**
- `total_requests == 0` sur 14 jours
- Cluster actif (state = READY)
- Age >7 jours (éviter faux positifs)

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
bigtable_admin_client.list_clusters(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/server/request_count"'
)
```

#### Calcul de Coût

**Formule :**

Instance idle = 100% waste :

```python
# Récupérer config cluster
node_count = cluster.serve_nodes
storage_type = cluster.default_storage_type

if storage_type == bigtable_admin_v2.StorageType.SSD:
    cost_per_node = 474
    storage_price = 0.17
else:
    cost_per_node = 226
    storage_price = 0.026

# Coût nodes
nodes_cost = node_count * cost_per_node

# Storage (minimal si idle)
storage_size_gb = get_storage_size(cluster)  # Via métriques
storage_cost = storage_size_gb * storage_price

# Backups
backup_size_gb = storage_size_gb * 1.5
backup_cost = backup_size_gb * 0.10

# Coût total = 100% waste
monthly_cost = nodes_cost + storage_cost + backup_cost

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Cluster 3 nodes SSD idle depuis 60 jours :
```python
nodes_cost = 3 * $474 = $1,422
storage_cost = 100 * $0.17 = $17
backup_cost = 150 * $0.10 = $15
monthly_cost = $1,454
already_wasted = $1,454 * (60/30) = $2,908
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 14 | Période analyse requests |
| `min_age_days` | int | 7 | Âge minimum cluster |
| `min_requests_threshold` | int | 0 | Requests min pour être actif |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-3333333333",
  "resource_name": "unused-bigtable-db",
  "resource_type": "bigtable_idle",
  "cluster_id": "cluster-europe-west1",
  "location": "europe-west1-b",
  "state": "READY",
  "storage_type": "SSD",
  "node_count": 3,
  "request_metrics": {
    "total_requests_14d": 0
  },
  "creation_time": "2024-09-05T10:00:00Z",
  "age_days": 58,
  "estimated_monthly_cost": 1454.00,
  "already_wasted": 2808.67,
  "confidence": "high",
  "recommendation": "Delete instance - zero requests in 14 days",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `bigtable_empty_tables` - Instances avec Tables Vides

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, lister tables
from google.cloud import bigtable_admin_v2

bigtable_table_admin_client = bigtable_admin_v2.BigtableTableAdminClient()

for instance in instances.instances:
    instance_name = instance.name

    # 3. Lister tables
    tables = bigtable_table_admin_client.list_tables(parent=instance_name)

    tables_list = list(tables)

    # 4. Vérifier si tables vides
    if len(tables_list) == 0:
        # Instance sans tables = waste évident
        continue

    # 5. Pour chaque table, vérifier taille storage
    empty_tables = 0

    for table in tables_list:
        table_name = table.name

        # Récupérer métriques storage
        # Note: Bigtable ne fournit pas métrique row count directe
        # Utiliser storage size comme proxy

        # Si storage table <1 GB = probablement vide/minimal
        # Via monitoring: bigtable.googleapis.com/table/bytes_used

        from google.cloud import monitoring_v3

        monitoring_client = monitoring_v3.MetricServiceClient()

        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 24*3600},  # 24h
        })

        table_id = table_name.split('/')[-1]

        storage_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="bigtable_table" AND resource.table="{table_id}" AND metric.type="bigtable.googleapis.com/table/bytes_used"',
                "interval": interval,
            }
        )

        storage_values = [
            point.value.int64_value
            for series in storage_metrics
            for point in series.points
        ]

        if storage_values:
            avg_storage_bytes = sum(storage_values) / len(storage_values)
            avg_storage_gb = avg_storage_bytes / (1024**3)

            if avg_storage_gb < 1.0:  # <1 GB = vide
                empty_tables += 1

    # 6. Détection si toutes tables vides
    if empty_tables == len(tables_list) and len(tables_list) > 0:
        # Instance avec tables vides = waste
```

**Critères :**
- Tables existent MAIS storage <1 GB par table (vides)
- Age >7 jours
- Cluster actif

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# Bigtable Table Admin API
bigtable_table_admin_client.list_tables(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/table/bytes_used"'
)
```

#### Calcul de Coût

**Formule :**

Tables vides = 100% waste (aucune donnée) :

```python
# Instance avec tables vides = inutilisée

# Récupérer config cluster
clusters = bigtable_admin_client.list_clusters(parent=instance_name)
cluster = list(clusters.clusters)[0]

node_count = cluster.serve_nodes
storage_type = cluster.default_storage_type

if storage_type == bigtable_admin_v2.StorageType.SSD:
    cost_per_node = 474
else:
    cost_per_node = 226

# Coût nodes
nodes_cost = node_count * cost_per_node

# Storage minimal (tables vides)
storage_cost = 5 * (0.17 if storage_type == bigtable_admin_v2.StorageType.SSD else 0.026)

# Backups
backup_cost = 10 * 0.10

# Coût total = 100% waste
monthly_cost = nodes_cost + storage_cost + backup_cost

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Instance 1 node HDD avec tables vides depuis 30 jours :
```python
nodes_cost = 1 * $226 = $226
storage_cost = 5 * $0.026 = $0.13
backup_cost = 10 * $0.10 = $1
monthly_cost = $227.13
already_wasted = $227.13 * (30/30) = $227.13
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 7 | Âge minimum instance |
| `empty_table_storage_threshold_gb` | float | 1.0 | Storage max pour table vide |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-8888888888",
  "resource_name": "empty-bigtable-instance",
  "resource_type": "bigtable_empty_tables",
  "cluster_id": "cluster-us-central1",
  "location": "us-central1-a",
  "state": "READY",
  "storage_type": "HDD",
  "node_count": 1,
  "tables": [
    {
      "table_id": "test-table",
      "storage_gb": 0.3,
      "is_empty": true
    }
  ],
  "total_tables": 1,
  "empty_tables": 1,
  "creation_time": "2024-10-03T10:00:00Z",
  "age_days": 30,
  "estimated_monthly_cost": 227.13,
  "already_wasted": 227.13,
  "confidence": "high",
  "recommendation": "Delete instance - all tables are empty",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `bigtable_untagged` - Instances Non Taguées

#### Détection

**Logique :**
```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque instance, vérifier labels
for instance in instances.instances:
    labels = instance.labels if hasattr(instance, 'labels') else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged instance = governance waste
```

**Critères :**
- Labels manquants parmi la liste requise

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Instances non taguées = perte de visibilité
# Coût estimé = 5% du coût instance

# Récupérer coût total instance
clusters = bigtable_admin_client.list_clusters(parent=instance.name)

total_monthly_cost = 0

for cluster in clusters.clusters:
    node_count = cluster.serve_nodes
    storage_type = cluster.default_storage_type

    if storage_type == bigtable_admin_v2.StorageType.SSD:
        cost_per_node = 474
    else:
        cost_per_node = 226

    total_monthly_cost += node_count * cost_per_node

# Governance waste = 5%
governance_waste_percentage = 0.05
monthly_waste = total_monthly_cost * governance_waste_percentage

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Instance 6 nodes SSD (2 clusters) sans labels depuis 180 jours :
```python
total_monthly_cost = 6 * $474 = $2,844
monthly_waste = $2,844 * 0.05 = $142.20
already_wasted = $142.20 * (180/30) = $853.20
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-1010101010",
  "resource_name": "unnamed-bigtable-47",
  "resource_type": "bigtable_untagged",
  "state": "READY",
  "clusters": [
    {
      "cluster_id": "cluster-us-central1",
      "node_count": 3,
      "storage_type": "SSD"
    },
    {
      "cluster_id": "cluster-us-east1",
      "node_count": 3,
      "storage_type": "SSD"
    }
  ],
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "creation_time": "2024-05-06T08:00:00Z",
  "age_days": 180,
  "instance_monthly_cost": 2844.00,
  "estimated_monthly_waste": 142.20,
  "already_wasted": 853.20,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `bigtable_low_cpu` - Nodes avec CPU Faible

#### Détection

**Logique :**

Analyser CPU pour right-sizing agressif :

```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque cluster, récupérer CPU détaillé (14 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances.instances:
    clusters = bigtable_admin_client.list_clusters(parent=instance.name)

    for cluster in clusters.clusters:
        cluster_id = cluster.name.split('/')[-1]
        node_count = cluster.serve_nodes

        # 3. Query CPU load
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 14*24*3600},
        })

        cpu_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="bigtable_cluster" AND resource.cluster="{cluster_id}" AND metric.type="bigtable.googleapis.com/cluster/cpu_load"',
                "interval": interval,
            }
        )

        cpu_values = [
            point.value.double_value
            for series in cpu_metrics
            for point in series.points
        ]

        avg_cpu = (sum(cpu_values) / len(cpu_values) * 100) if cpu_values else 0

        # 4. Détection si CPU <20% (très sous-utilisé)
        if avg_cpu < cpu_threshold:
            # Recommandation agressive: réduire nodes
            # Bigtable optimal = 70% CPU
            # Si 15% CPU → réduire à ~20% des nodes actuels

            optimal_nodes = max(1, int(node_count * (avg_cpu / 70.0)))

            # Low CPU = waste significatif
```

**Critères :**
- `avg_cpu < 20%` sur 14 jours
- Cluster actif (state = READY)
- Recommandation: réduction agressive nodes

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_instances(parent=f"projects/{project_id}")
bigtable_admin_client.list_clusters(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/cluster/cpu_load"'
)
```

#### Calcul de Coût

**Formule :**

CPU <20% = opportunité réduction massive :

```python
# Exemple: 10 nodes SSD avec CPU 15%

current_nodes = 10
avg_cpu = 15.0
storage_type = 'SSD'
cost_per_node = 474

# Nodes optimal pour 70% CPU
optimal_nodes = max(1, int(10 * (15.0 / 70.0)))  # 2 nodes
optimal_nodes = 2

current_cost = 10 * 474 = $4,740
optimal_cost = 2 * 474 = $948

# Waste
monthly_waste = $4,740 - $948 = $3,792

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster 10 nodes SSD avec CPU 15% depuis 90 jours :
```python
current_cost = $4,740/mois
optimal_cost = $948/mois (2 nodes)
monthly_waste = $3,792
already_wasted = $3,792 * (90/30) = $11,376
savings_percentage = 80%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `cpu_threshold` | float | 20.0 | CPU % maximum |
| `target_cpu` | float | 70.0 | CPU optimal Bigtable |
| `lookback_days` | int | 14 | Période analyse |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-2020202020",
  "resource_name": "low-traffic-bigtable",
  "resource_type": "bigtable_low_cpu",
  "cluster_id": "cluster-asia-southeast1",
  "location": "asia-southeast1-a",
  "state": "READY",
  "storage_type": "SSD",
  "node_count": 10,
  "cpu_metrics": {
    "avg_cpu_14d": 16.2,
    "max_cpu_14d": 31.8
  },
  "recommended_node_count": 2,
  "current_cost_monthly": 4740.00,
  "recommended_cost_monthly": 948.00,
  "estimated_monthly_waste": 3792.00,
  "already_wasted": 11376.00,
  "savings_percentage": 80,
  "confidence": "high",
  "recommendation": "Reduce from 10 nodes to 2 nodes (80% cost savings)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `bigtable_storage_type_suboptimal` - Storage Type Suboptimal

#### Détection

**Logique :**

Analyser pattern accès pour optimiser storage type :

```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque cluster, analyser read pattern
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for instance in instances.instances:
    clusters = bigtable_admin_client.list_clusters(parent=instance.name)

    for cluster in clusters.clusters:
        cluster_id = cluster.name.split('/')[-1]
        storage_type = cluster.default_storage_type

        # 3. Si SSD, vérifier si HDD suffirait
        if storage_type == bigtable_admin_v2.StorageType.SSD:
            # Query read latency percentiles
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(time.time())},
                "start_time": {"seconds": int(time.time()) - 14*24*3600},
            })

            latency_metrics = monitoring_client.list_time_series(
                request={
                    "name": f"projects/{project_id}",
                    "filter": f'resource.type="bigtable_cluster" AND resource.cluster="{cluster_id}" AND metric.type="bigtable.googleapis.com/server/latencies"',
                    "interval": interval,
                }
            )

            # Calculer p99 latency
            latencies = [
                point.value.distribution_value.mean
                for series in latency_metrics
                for point in series.points
            ]

            if latencies:
                p99_latency_ms = sorted(latencies)[int(len(latencies) * 0.99)]

                # Si p99 latency <50ms et read throughput faible
                # HDD suffit (latency <100ms acceptable)

                if p99_latency_ms < 50:
                    # Storage type suboptimal, HDD suffit
```

**Critères :**
- `storage_type == 'SSD'`
- P99 latency <50ms (HDD offre <100ms)
- Read throughput <100 reads/sec/node

**API Calls :**
```python
# Bigtable Admin API
bigtable_admin_client.list_clusters(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/server/latencies"'
)
```

#### Calcul de Coût

**Formule :**

SSD → HDD (latency acceptable) = -64% coût :

```python
# Exemple: 3 nodes SSD, 10 TB, latency OK pour HDD

node_count = 3
storage_size_gb = 10000

# SSD costs
ssd_nodes_cost = 3 * 474 = $1,422
ssd_storage_cost = 10000 * 0.17 = $1,700
ssd_total = $3,122

# HDD costs
hdd_nodes_cost = 3 * 226 = $678
hdd_storage_cost = 10000 * 0.026 = $260
hdd_total = $938

# Waste
monthly_waste = $3,122 - $938 = $2,184

# Coût gaspillé
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Cluster 3 nodes SSD avec 10 TB (latency OK) depuis 120 jours :
```python
ssd_cost = $3,122/mois
hdd_cost = $938/mois
monthly_waste = $2,184
already_wasted = $2,184 * (120/30) = $8,736
savings_percentage = 70%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `max_latency_threshold_ms` | float | 50.0 | Latency max pour HDD recommendation |
| `lookback_days` | int | 14 | Période analyse latency |
| `min_savings_threshold` | float | 200.0 | Économie min $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-3030303030",
  "resource_name": "archive-bigtable",
  "resource_type": "bigtable_storage_type_suboptimal",
  "cluster_id": "cluster-us-west1",
  "location": "us-west1-a",
  "state": "READY",
  "storage_type": "SSD",
  "node_count": 3,
  "storage_size_gb": 10000,
  "latency_metrics": {
    "p50_latency_ms": 8.2,
    "p99_latency_ms": 42.1
  },
  "current_cost_monthly": 3122.00,
  "recommended_storage_type": "HDD",
  "recommended_cost_monthly": 938.00,
  "estimated_monthly_waste": 2184.00,
  "already_wasted": 8736.00,
  "savings_percentage": 70,
  "confidence": "high",
  "recommendation": "Migrate to HDD - p99 latency 42ms (acceptable for HDD <100ms)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `bigtable_zero_read_tables` - Tables avec Zero Reads

#### Détection

**Logique :**

Identifier tables jamais lues (archivage recommandé) :

```python
# 1. Lister toutes les instances
instances = bigtable_admin_client.list_instances(parent=f"projects/{project_id}")

# 2. Pour chaque instance, lister tables
from google.cloud import bigtable_admin_v2

bigtable_table_admin_client = bigtable_admin_v2.BigtableTableAdminClient()

for instance in instances.instances:
    tables = bigtable_table_admin_client.list_tables(parent=instance.name)

    # 3. Pour chaque table, récupérer métriques read (30 jours)
    from google.cloud import monitoring_v3

    monitoring_client = monitoring_v3.MetricServiceClient()

    zero_read_tables = []

    for table in tables:
        table_id = table.name.split('/')[-1]

        # 4. Query read count
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(time.time())},
            "start_time": {"seconds": int(time.time()) - 30*24*3600},
        })

        read_metrics = monitoring_client.list_time_series(
            request={
                "name": f"projects/{project_id}",
                "filter": f'resource.type="bigtable_table" AND resource.table="{table_id}" AND metric.type="bigtable.googleapis.com/server/request_count" AND metric.label.method="Bigtable.ReadRows"',
                "interval": interval,
            }
        )

        total_reads = sum([
            point.value.int64_value
            for series in read_metrics
            for point in series.points
        ])

        # 5. Détection si zero reads
        if total_reads == 0:
            # Récupérer taille table
            storage_metrics = get_table_storage_size(table_id)

            zero_read_tables.append({
                'table_id': table_id,
                'storage_gb': storage_metrics
            })

    # 6. Si tables jamais lues, archivage recommandé
    if len(zero_read_tables) > 0:
        # Tables zero reads = waste storage
```

**Critères :**
- `total_reads == 0` sur 30 jours
- Table avec données (storage >1 GB)
- Recommandation: export vers Cloud Storage (90% moins cher)

**API Calls :**
```python
# Bigtable Table Admin API
bigtable_table_admin_client.list_tables(parent=instance_name)

# Cloud Monitoring API
monitoring_client.list_time_series(
    filter='metric.type="bigtable.googleapis.com/server/request_count"'
)
```

#### Calcul de Coût

**Formule :**

Table jamais lue → Archive Cloud Storage :

```python
# Exemple: Table 1 TB jamais lue (SSD)

table_storage_gb = 1000
storage_type = 'SSD'

# Coût actuel (Bigtable SSD)
bigtable_storage_cost = 1000 * 0.17 = $170/mois

# Coût recommandé (Cloud Storage Nearline)
cloud_storage_cost = 1000 * 0.010 = $10/mois

# Waste = différence
monthly_waste = $170 - $10 = $160

# Note: Export one-time puis suppression table
# Économie ongoing

# Coût gaspillé (derniers 6 mois sans lecture)
months_zero_reads = 6
already_wasted = monthly_waste * months_zero_reads
```

**Exemple :**

Table 1 TB SSD jamais lue depuis 6 mois :
```python
bigtable_cost = $170/mois
cloud_storage_cost = $10/mois (Nearline)
monthly_waste = $160
already_wasted = $160 * 6 = $960
savings_percentage = 94%
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 30 | Période analyse reads |
| `min_table_size_gb` | float | 1.0 | Taille min table pour détection |
| `archive_storage_class` | str | `'NEARLINE'` | Cloud Storage class recommandée |

#### Métadonnées Exemple

```json
{
  "resource_id": "instance-4040404040",
  "resource_name": "prod-bigtable-with-cold-tables",
  "resource_type": "bigtable_zero_read_tables",
  "cluster_id": "cluster-us-central1",
  "state": "READY",
  "storage_type": "SSD",
  "zero_read_tables": [
    {
      "table_id": "archived-events-2023",
      "storage_gb": 1200,
      "last_read_date": null,
      "zero_read_days": 180
    }
  ],
  "total_zero_read_storage_gb": 1200,
  "current_storage_cost_monthly": 204.00,
  "recommended_archive_cost_monthly": 12.00,
  "estimated_monthly_waste": 192.00,
  "already_wasted": 1152.00,
  "confidence": "medium",
  "recommendation": "Export tables to Cloud Storage Nearline and delete from Bigtable",
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
gcloud services enable bigtableadmin.googleapis.com
gcloud services enable bigtable.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account

```bash
# Ajouter permissions Bigtable
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigtable.reader"

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

#### 3. Installer cbt CLI

```bash
# macOS
gcloud components install cbt

# Configuration cbt
echo "project = $PROJECT_ID" > ~/.cbtrc
echo "instance = test-instance" >> ~/.cbtrc
```

---

### Tests Unitaires - Créer Instances de Test

#### Scénario 1: Instance Sous-Utilisée

```bash
# Créer instance avec 6 nodes SSD
gcloud bigtable instances create test-underutilized-instance \
  --display-name="Test underutilized" \
  --cluster=cluster-us-central1 \
  --cluster-zone=us-central1-a \
  --cluster-num-nodes=6 \
  --cluster-storage-type=SSD

# Créer table et générer très faible charge
cbt -instance=test-underutilized-instance createtable test-table
cbt -instance=test-underutilized-instance createfamily test-table cf1

# Attendre 14 jours avec faible utilisation
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_underutilized",
  "node_count": 6,
  "storage_type": "SSD",
  "cpu_metrics": {"avg_cpu_14d": "<30"},
  "estimated_monthly_waste": "~1896"
}
```

---

#### Scénario 2: Multi-Cluster Inutile

```bash
# Créer instance multi-cluster pour dev
gcloud bigtable instances create test-multicluster-dev \
  --display-name="Test multi-cluster dev" \
  --cluster=cluster-us-central1 \
  --cluster-zone=us-central1-a \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD \
  --instance-labels=environment=dev,team=data

# Ajouter replica cluster
gcloud bigtable clusters create cluster-us-east1 \
  --instance=test-multicluster-dev \
  --zone=us-east1-b \
  --num-nodes=3
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_unnecessary_multicluster",
  "labels": {"environment": "dev"},
  "total_nodes": 6,
  "estimated_monthly_waste": "~1422"
}
```

---

#### Scénario 3: SSD Storage Inutile

```bash
# Créer instance SSD avec low reads
gcloud bigtable instances create test-unnecessary-ssd \
  --display-name="Test SSD unnecessary" \
  --cluster=cluster-us-west1 \
  --cluster-zone=us-west1-a \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD

# Créer table avec données mais low read throughput
cbt -instance=test-unnecessary-ssd createtable archive-table
cbt -instance=test-unnecessary-ssd createfamily archive-table cf1

# Attendre 14 jours avec <100 reads/sec/node
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_unnecessary_ssd",
  "storage_type": "SSD",
  "read_metrics": {"avg_reads_per_sec_per_node": "<100"},
  "estimated_monthly_waste": "~1464"
}
```

---

#### Scénario 4: Dev/Test Over-Provisioned

```bash
# Créer instance dev avec config production
gcloud bigtable instances create test-devtest-large \
  --display-name="Test dev large" \
  --cluster=cluster-us-central1 \
  --cluster-zone=us-central1-a \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD \
  --instance-labels=environment=dev
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_devtest_overprovisioned",
  "labels": {"environment": "dev"},
  "node_count": 3,
  "storage_type": "SSD",
  "estimated_monthly_waste": "~1196"
}
```

---

#### Scénario 5: Instance Idle

```bash
# Créer instance
gcloud bigtable instances create test-idle-instance \
  --display-name="Test idle" \
  --cluster=cluster-europe-west1 \
  --cluster-zone=europe-west1-b \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD

# NE PAS créer de tables ni générer de traffic

# Attendre 14 jours sans requests
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_idle",
  "request_metrics": {"total_requests_14d": 0},
  "estimated_monthly_cost": "~1454"
}
```

---

#### Scénario 6: Tables Vides

```bash
# Créer instance
gcloud bigtable instances create test-empty-tables \
  --display-name="Test empty tables" \
  --cluster=cluster-us-central1 \
  --cluster-zone=us-central1-a \
  --cluster-num-nodes=1 \
  --cluster-storage-type=HDD

# Créer tables SANS données
cbt -instance=test-empty-tables createtable empty-table
cbt -instance=test-empty-tables createfamily empty-table cf1

# Ne pas insérer de données

# Attendre 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_empty_tables",
  "total_tables": 1,
  "empty_tables": 1,
  "estimated_monthly_cost": "~227"
}
```

---

#### Scénario 7: Instance Non Taguée

```bash
# Créer instance SANS labels
gcloud bigtable instances create test-untagged-instance \
  --display-name="Test untagged" \
  --cluster=cluster-us-central1 \
  --cluster-zone=us-central1-a \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_untagged",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "estimated_monthly_waste": "~71.10"
}
```

---

#### Scénario 8: Nodes avec CPU Faible

```bash
# Créer instance large
gcloud bigtable instances create test-low-cpu \
  --display-name="Test low CPU" \
  --cluster=cluster-asia-southeast1 \
  --cluster-zone=asia-southeast1-a \
  --cluster-num-nodes=10 \
  --cluster-storage-type=SSD

# Créer table avec charge très légère (CPU <20%)
cbt -instance=test-low-cpu createtable test-table
cbt -instance=test-low-cpu createfamily test-table cf1

# Attendre 14 jours avec charge minimale
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_low_cpu",
  "node_count": 10,
  "cpu_metrics": {"avg_cpu_14d": "<20"},
  "estimated_monthly_waste": "~3792"
}
```

---

#### Scénario 9: Storage Type Suboptimal

```bash
# Créer instance SSD avec latency OK pour HDD
gcloud bigtable instances create test-storage-suboptimal \
  --display-name="Test storage suboptimal" \
  --cluster=cluster-us-west1 \
  --cluster-zone=us-west1-a \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD

# Créer table avec données cold
cbt -instance=test-storage-suboptimal createtable archive-table
cbt -instance=test-storage-suboptimal createfamily archive-table cf1

# Attendre 14 jours avec latency <50ms p99
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_storage_type_suboptimal",
  "storage_type": "SSD",
  "latency_metrics": {"p99_latency_ms": "<50"},
  "estimated_monthly_waste": "~2184"
}
```

---

#### Scénario 10: Tables avec Zero Reads

```bash
# Créer instance
gcloud bigtable instances create test-zero-read-tables \
  --display-name="Test zero read tables" \
  --cluster=cluster-us-central1 \
  --cluster-zone=us-central1-a \
  --cluster-num-nodes=3 \
  --cluster-storage-type=SSD

# Créer table avec données mais AUCUN read
cbt -instance=test-zero-read-tables createtable cold-table
cbt -instance=test-zero-read-tables createfamily cold-table cf1

# Insérer données (writes) mais AUCUN read

# Attendre 30 jours sans reads
```

**Validation attendue :**
```json
{
  "resource_type": "bigtable_zero_read_tables",
  "zero_read_tables": 1,
  "total_zero_read_storage_gb": ">1",
  "estimated_monthly_waste": "~192"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script validation Cloud Bigtable
"""

from google.cloud import bigtable_admin_v2
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    bigtable_admin_client = bigtable_admin_v2.BigtableInstanceAdminClient()

    # Lister instances
    instances = bigtable_admin_client.list_instances(parent=f"projects/{PROJECT_ID}")

    instances_list = list(instances.instances)
    print(f"✅ Found {len(instances_list)} Cloud Bigtable instances")

    scenarios_detected = {
        'underutilized': 0,
        'unnecessary_multicluster': 0,
        'unnecessary_ssd': 0,
        'devtest_overprovisioned': 0,
        'idle': 0,
        'empty_tables': 0,
        'untagged': 0,
        'low_cpu': 0,
        'storage_type_suboptimal': 0,
        'zero_read_tables': 0,
    }

    for instance in instances_list:
        name = instance.name.split('/')[-1]

        # Scenario 2: Multi-cluster inutile
        clusters = bigtable_admin_client.list_clusters(parent=instance.name)
        clusters_list = list(clusters.clusters)

        if len(clusters_list) >= 2:
            labels = instance.labels if hasattr(instance, 'labels') else {}
            if labels.get('environment') in ['dev', 'test']:
                scenarios_detected['unnecessary_multicluster'] += 1
                print(f"✅ Detected scenario 2 (multi-cluster dev): {name}")

        # Scenario 4: Dev/test over-provisioned
        labels = instance.labels if hasattr(instance, 'labels') else {}
        if labels.get('environment') in ['dev', 'test']:
            for cluster in clusters_list:
                if cluster.serve_nodes >= 3 or cluster.default_storage_type == bigtable_admin_v2.StorageType.SSD:
                    scenarios_detected['devtest_overprovisioned'] += 1
                    print(f"✅ Detected scenario 4 (dev/test over-provisioned): {name}")
                    break

        # Scenario 7: Untagged
        if not labels or len(labels) == 0:
            scenarios_detected['untagged'] += 1
            print(f"✅ Detected scenario 7 (untagged): {name}")

    # Rapport
    print("\n📊 Detection Summary:")
    for scenario, count in scenarios_detected.items():
        print(f"  - {scenario}: {count} instances")

    print(f"\n✅ Total waste detected: {sum(scenarios_detected.values())} instances")

if __name__ == '__main__':
    test_all_scenarios()
```

---

### Cleanup

```bash
# Supprimer toutes instances test
gcloud bigtable instances delete test-underutilized-instance --quiet
gcloud bigtable instances delete test-multicluster-dev --quiet
gcloud bigtable instances delete test-unnecessary-ssd --quiet
gcloud bigtable instances delete test-devtest-large --quiet
gcloud bigtable instances delete test-idle-instance --quiet
gcloud bigtable instances delete test-empty-tables --quiet
gcloud bigtable instances delete test-untagged-instance --quiet
gcloud bigtable instances delete test-low-cpu --quiet
gcloud bigtable instances delete test-storage-suboptimal --quiet
gcloud bigtable instances delete test-zero-read-tables --quiet
```

---

## Références

### Documentation GCP

- [Cloud Bigtable API](https://cloud.google.com/bigtable/docs/reference/admin/rest)
- [Cloud Bigtable Pricing](https://cloud.google.com/bigtable/pricing)
- [SSD vs HDD Storage](https://cloud.google.com/bigtable/docs/choosing-ssd-hdd)
- [Monitoring Metrics](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-bigtable)
- [Performance Guide](https://cloud.google.com/bigtable/docs/performance)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md)
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md)
- [GCP_GKE_CLUSTER_SCENARIOS_100.md](./GCP_GKE_CLUSTER_SCENARIOS_100.md)
- [GCP_CLOUD_SQL_SCENARIOS_100.md](./GCP_CLOUD_SQL_SCENARIOS_100.md)
- [GCP_CLOUD_SPANNER_SCENARIOS_100.md](./GCP_CLOUD_SPANNER_SCENARIOS_100.md)

### Équivalences AWS/Azure

- **AWS DynamoDB** → GCP Cloud Bigtable
- **Azure Cosmos DB (Cassandra)** → GCP Cloud Bigtable
- **Apache HBase** → GCP Cloud Bigtable (managed)
- **Apache Cassandra** → GCP Cloud Bigtable (architecture similar)

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
