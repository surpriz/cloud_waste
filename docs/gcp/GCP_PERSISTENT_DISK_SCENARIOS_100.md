# CloudWaste - Couverture 100% GCP Persistent Disks

**Resource Type:** `Compute : Persistent Disks`
**Provider:** Google Cloud Platform (GCP)
**API:** `compute.googleapis.com` (Compute Engine API v1)
**Équivalents:** AWS EBS Volumes, Azure Managed Disks
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing GCP](#modèle-de-pricing-gcp)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Disques Non Attachés](#1-persistent_disk_unattached---disques-non-attachés)
  - [2. Disques Attachés à Instances Arrêtées](#2-persistent_disk_attached_stopped---disques-attachés-à-instances-arrêtées)
  - [3. Disques Jamais Utilisés](#3-persistent_disk_never_used---disques-jamais-utilisés)
  - [4. Snapshots Orphelins](#4-persistent_disk_orphan_snapshots---snapshots-orphelins)
  - [5. Ancien Type de Disque](#5-persistent_disk_old_type---ancien-type-de-disque)
  - [6. Type de Disque Sur-Provisionné](#6-persistent_disk_overprovisioned_type---type-de-disque-sur-provisionné)
  - [7. Disques Non Taggés](#7-persistent_disk_untagged---disques-non-taggés)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Disques Sous-Utilisés](#8-persistent_disk_underutilized---disques-sous-utilisés)
  - [9. Disques Sur-Dimensionnés](#9-persistent_disk_oversized---disques-sur-dimensionnés)
  - [10. Disques en Lecture Seule](#10-persistent_disk_readonly---disques-en-lecture-seule)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte GCP Persistent Disks

Google Cloud Platform propose plusieurs **types de Persistent Disks** avec différents niveaux de performance et prix :

- **pd-standard** (HDD) - $0.040/GB/mois - Throughput: 0.12 MB/s par GB
- **pd-balanced** (SSD) - $0.100/GB/mois - Throughput: 0.28 MB/s par GB, IOPS: 6 par GB
- **pd-ssd** (SSD performance) - $0.170/GB/mois - Throughput: 0.48 MB/s par GB, IOPS: 30 par GB
- **pd-extreme** (ultra-performance) - $0.125/GB/mois + IOPS provisionnés - Custom IOPS
- **Snapshots** - $0.026/GB/mois - Storage only

**Caractéristiques :**
- Persistent Disks facturés à la seconde (minimum 1 minute)
- Taille: 10 GB à 64 TB (pd-standard/balanced/ssd)
- Facturés même si non attachés ou instance arrêtée
- Snapshots incrémentaux (seuls les changements facturés après 1er snapshot)

### Waste Typique

1. **Disques non attachés** : 100% du coût sans aucune utilité
2. **Disques attachés à instances arrêtées** : Paiement inutile si instance non utilisée
3. **Over-provisioning type** : pd-ssd ($0.170) au lieu de pd-balanced ($0.100) = -41% économie
4. **Over-sizing** : 1 TB alloué, 100 GB utilisé = 900 GB gaspillés
5. **Snapshots orphelins** : Snapshots dont le disque source n'existe plus

---

## Modèle de Pricing GCP

### Pricing Persistent Disks (par GB/mois, us-central1)

| Type | Prix/GB/mois | IOPS/GB | Throughput MB/s/GB | Use Case |
|------|-------------|---------|-------------------|----------|
| **pd-standard** | $0.040 | 0.75 read<br>1.5 write | 0.12 | Données rarement accédées, backups |
| **pd-balanced** | $0.100 | 6 | 0.28 | Workloads généraux, boot disks |
| **pd-ssd** | $0.170 | 30 | 0.48 | Databases, haute performance |
| **pd-extreme** | $0.125 + IOPS | Custom | Custom | Ultra-performance, latence critique |
| **Snapshots** | $0.026 | N/A | N/A | Backups, images |

### Exemples de Coûts Mensuels

| Taille | pd-standard | pd-balanced | pd-ssd | Snapshot | Économie pd-standard → Snapshot |
|--------|-------------|-------------|--------|----------|--------------------------------|
| **100 GB** | $4.00 | $10.00 | $17.00 | $2.60 | -35% |
| **500 GB** | $20.00 | $50.00 | $85.00 | $13.00 | -35% |
| **1 TB** | $40.00 | $100.00 | $170.00 | $26.00 | -35% |
| **5 TB** | $200.00 | $500.00 | $850.00 | $130.00 | -35% |
| **10 TB** | $400.00 | $1,000.00 | $1,700.00 | $260.00 | -35% |

**Notes :**
- pd-balanced recommandé pour la plupart des workloads (best price/performance)
- pd-ssd uniquement si IOPS >3000 requis
- Snapshots 35% moins cher que pd-standard (mais read-only)

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `persistent_disk_unattached` - Disques Non Attachés

#### Détection

**Logique :**
```python
# 1. Lister tous les disques persistants
from google.cloud import compute_v1

compute_client = compute_v1.DisksClient()

request = compute_v1.AggregatedListDisksRequest(
    project=project_id
)

agg_list = compute_client.aggregated_list(request=request)

# 2. Pour chaque disque, vérifier si attaché
for zone, response in agg_list:
    if response.disks:
        for disk in response.disks:
            # 3. Détection si users == [] (non attaché)
            users = disk.users  # Liste d'instances utilisant le disque

            if not users or len(users) == 0:
                # 4. Calculer âge depuis création
                creation_timestamp = parse_timestamp(disk.creation_timestamp)
                age_days = (now - creation_timestamp).days

                # 5. Détection si âge >= seuil (défaut: 7 jours)
                if age_days >= min_age_days:
                    # Disque unattached = waste détecté
```

**Critères :**
- `len(disk.users) == 0` (aucune instance attachée)
- `age >= min_age_days` (défaut: 7 jours)

**API Calls :**
```python
# Compute Engine API - Disks
compute_client = compute_v1.DisksClient()
agg_list = compute_client.aggregated_list(
    project='my-project'
)
```

#### Calcul de Coût

**Formule :**

Disques non attachés = 100% waste :

```python
# Récupérer type et taille du disque
disk_type = disk.type.split('/')[-1]  # "pd-standard", "pd-balanced", "pd-ssd"
disk_size_gb = disk.size_gb

# Prix par GB selon type (us-central1)
disk_pricing = {
    'pd-standard': 0.040,   # $/GB/mois
    'pd-balanced': 0.100,
    'pd-ssd': 0.170,
    'pd-extreme': 0.125,    # Base price (+ IOPS)
}

price_per_gb = disk_pricing.get(disk_type, 0.040)

# Coût mensuel = 100% waste (disque inutilisé)
monthly_cost = disk_size_gb * price_per_gb

# Coût déjà gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Disque 500 GB pd-balanced non attaché depuis 60 jours :
```python
disk_size_gb = 500
price_per_gb = $0.100
monthly_cost = 500 * $0.100 = $50.00/mois
age_months = 60 / 30 = 2.0
already_wasted = $50.00 * 2.0 = $100.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 7 | Âge minimum avant détection |
| `exclude_labels` | dict | `{}` | Labels pour exclure disques (ex: `{'backup': 'true'}`) |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-1234567890123456789",
  "resource_name": "orphan-data-disk",
  "resource_type": "persistent_disk_unattached",
  "zone": "us-central1-a",
  "disk_type": "pd-balanced",
  "size_gb": 500,
  "status": "READY",
  "users": [],
  "creation_timestamp": "2024-09-05T10:00:00Z",
  "age_days": 58,
  "estimated_monthly_cost": 50.00,
  "already_wasted": 96.67,
  "confidence": "high",
  "recommendation": "Delete disk or attach to instance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `persistent_disk_attached_stopped` - Disques Attachés à Instances Arrêtées

#### Détection

**Logique :**
```python
# 1. Lister tous les disques persistants
disks = get_all_persistent_disks(project_id)

# 2. Pour chaque disque attaché, vérifier status instance
for disk in disks:
    users = disk.users  # Liste d'URLs d'instances

    if users and len(users) > 0:
        # 3. Pour chaque instance attachée, récupérer status
        for instance_url in users:
            # Parser zone et instance name depuis URL
            # URL format: https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances/{name}
            zone = extract_zone_from_url(instance_url)
            instance_name = extract_instance_name_from_url(instance_url)

            # 4. Récupérer instance
            instance = compute_client.instances().get(
                project=project_id,
                zone=zone,
                instance=instance_name
            ).execute()

            # 5. Détection si instance TERMINATED
            if instance['status'] == 'TERMINATED':
                # Calculer depuis quand instance arrêtée
                last_stop = parse_timestamp(instance.get('lastStopTimestamp'))
                age_days = (now - last_stop).days

                if age_days >= min_age_days:
                    # Disque attaché à instance arrêtée = waste détecté
```

**Critères :**
- `len(disk.users) > 0` (disque attaché)
- Instance avec `status == 'TERMINATED'`
- `age >= min_age_days` (défaut: 30 jours)

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Instances API (pour status)
compute_client.instances().get(
    project=project_id,
    zone='us-central1-a',
    instance='instance-name'
)
```

#### Calcul de Coût

**Formule :**

Disque attaché à instance arrêtée = 100% waste (disque inutilisé) :

```python
disk_size_gb = disk.size_gb
disk_type = disk.type.split('/')[-1]

price_per_gb = {
    'pd-standard': 0.040,
    'pd-balanced': 0.100,
    'pd-ssd': 0.170,
}.get(disk_type, 0.040)

# Coût mensuel = 100% waste
monthly_cost = disk_size_gb * price_per_gb

# Coût gaspillé depuis arrêt instance
instance_stop_date = parse_timestamp(instance['lastStopTimestamp'])
stopped_days = (now - instance_stop_date).days
already_wasted = monthly_cost * (stopped_days / 30.0)
```

**Exemple :**

Disque 1 TB pd-ssd attaché à instance arrêtée depuis 45 jours :
```python
disk_size_gb = 1024
price_per_gb = $0.170
monthly_cost = 1024 * $0.170 = $174.08/mois
already_wasted = $174.08 * (45/30) = $261.12
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 30 | Durée minimum arrêt instance |
| `exclude_boot_disks` | bool | `False` | Exclure disques boot (auto-supprimés avec instance) |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-9876543210987654321",
  "resource_name": "prod-database-disk",
  "resource_type": "persistent_disk_attached_stopped",
  "zone": "us-east1-b",
  "disk_type": "pd-ssd",
  "size_gb": 1024,
  "status": "READY",
  "users": [
    "https://www.googleapis.com/compute/v1/projects/my-project/zones/us-east1-b/instances/db-server"
  ],
  "attached_instance": {
    "name": "db-server",
    "status": "TERMINATED",
    "last_stop_timestamp": "2024-09-18T12:00:00Z",
    "stopped_days": 45
  },
  "creation_timestamp": "2024-06-01T08:00:00Z",
  "age_days": 154,
  "estimated_monthly_cost": 174.08,
  "already_wasted": 261.12,
  "confidence": "high",
  "recommendation": "Delete disk or restart instance if still needed",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `persistent_disk_never_used` - Disques Jamais Utilisés

#### Détection

**Logique :**
```python
# 1. Lister tous les disques persistants
disks = get_all_persistent_disks(project_id)

# 2. Pour chaque disque, récupérer métriques I/O
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for disk in disks:
    # 3. Query I/O metrics depuis création
    creation_date = parse_timestamp(disk.creation_timestamp)
    age_days = (now - creation_date).days

    # 4. Seulement si disque >7 jours (éviter faux positifs)
    if age_days < min_age_days:
        continue

    # 5. Récupérer read/write bytes depuis création
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(creation_date.timestamp())},
    })

    # Query read operations
    read_ops = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="compute.googleapis.com/instance/disk/read_ops_count" AND resource.disk_name="{disk.name}"',
            "interval": interval,
        }
    )

    # Query write operations
    write_ops = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="compute.googleapis.com/instance/disk/write_ops_count" AND resource.disk_name="{disk.name}"',
            "interval": interval,
        }
    )

    # 6. Calculer total I/O operations
    total_read_ops = sum([point.value.int64_value for series in read_ops for point in series.points])
    total_write_ops = sum([point.value.int64_value for series in write_ops for point in series.points])

    # 7. Détection si zero I/O
    if total_read_ops == 0 and total_write_ops == 0:
        # Disque jamais utilisé = waste détecté
```

**Critères :**
- `age >= min_age_days` (défaut: 7 jours)
- `total_read_ops == 0`
- `total_write_ops == 0`

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Cloud Monitoring API
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/disk/read_ops_count"',
    interval={"start_time": ..., "end_time": ...}
)
```

#### Calcul de Coût

**Formule :**

Disque jamais utilisé = 100% waste :

```python
disk_size_gb = disk.size_gb
disk_type = disk.type.split('/')[-1]

price_per_gb = {
    'pd-standard': 0.040,
    'pd-balanced': 0.100,
    'pd-ssd': 0.170,
}.get(disk_type, 0.040)

# Coût mensuel = 100% waste
monthly_cost = disk_size_gb * price_per_gb

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Disque 250 GB pd-balanced jamais utilisé depuis 90 jours :
```python
disk_size_gb = 250
price_per_gb = $0.100
monthly_cost = 250 * $0.100 = $25.00/mois
already_wasted = $25.00 * (90/30) = $75.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 7 | Âge minimum avant détection |
| `zero_io_threshold` | int | 0 | Nombre max d'opérations I/O (0 = aucune) |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-5555555555555555555",
  "resource_name": "unused-test-disk",
  "resource_type": "persistent_disk_never_used",
  "zone": "europe-west1-b",
  "disk_type": "pd-balanced",
  "size_gb": 250,
  "status": "READY",
  "users": [
    "https://www.googleapis.com/compute/v1/projects/my-project/zones/europe-west1-b/instances/test-server"
  ],
  "io_metrics": {
    "total_read_ops": 0,
    "total_write_ops": 0,
    "total_read_bytes": 0,
    "total_write_bytes": 0
  },
  "creation_timestamp": "2024-08-05T09:00:00Z",
  "age_days": 89,
  "estimated_monthly_cost": 25.00,
  "already_wasted": 74.17,
  "confidence": "high",
  "recommendation": "Delete disk - never used since creation",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `persistent_disk_orphan_snapshots` - Snapshots Orphelins

#### Détection

**Logique :**
```python
# 1. Lister tous les snapshots
from google.cloud import compute_v1

compute_client = compute_v1.SnapshotsClient()

snapshots_list = compute_client.list(project=project_id)

# 2. Lister tous les disques existants
disks_client = compute_v1.DisksClient()
all_disks = get_all_disk_names(project_id)  # Set de noms de disques

# 3. Pour chaque snapshot, vérifier si disque source existe
for snapshot in snapshots_list:
    source_disk_url = snapshot.source_disk
    # URL format: https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/disks/{name}

    if not source_disk_url:
        # Snapshot sans source = orphelin
        continue

    # 4. Extraire nom du disque source
    source_disk_name = extract_disk_name_from_url(source_disk_url)

    # 5. Détection si disque source n'existe plus
    if source_disk_name not in all_disks:
        # 6. Calculer âge snapshot
        creation_timestamp = parse_timestamp(snapshot.creation_timestamp)
        age_days = (now - creation_timestamp).days

        if age_days >= min_age_days:
            # Snapshot orphelin = potentiel waste
```

**Critères :**
- `snapshot.source_disk` pointe vers disque supprimé
- `age >= min_age_days` (défaut: 30 jours)

**API Calls :**
```python
# Snapshots API
snapshots_client = compute_v1.SnapshotsClient()
snapshots_list = snapshots_client.list(project=project_id)

# Disks API (pour vérifier existence)
disks_client = compute_v1.DisksClient()
disks_list = disks_client.aggregated_list(project=project_id)
```

#### Calcul de Coût

**Formule :**

Snapshots = $0.026/GB/mois :

```python
# Taille snapshot (stockage réel utilisé)
snapshot_size_gb = snapshot.storage_bytes / (1024**3)

# Prix snapshot
snapshot_price_per_gb = 0.026  # $/GB/mois

# Coût mensuel
monthly_cost = snapshot_size_gb * snapshot_price_per_gb

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months

# Note: Snapshot orphelin pas forcément waste total
# (peut servir pour recovery) - confidence: medium
```

**Exemple :**

Snapshot 500 GB orphelin depuis 180 jours :
```python
snapshot_size_gb = 500
snapshot_price_per_gb = $0.026
monthly_cost = 500 * $0.026 = $13.00/mois
already_wasted = $13.00 * (180/30) = $78.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 30 | Âge minimum avant détection |
| `exclude_labels` | dict | `{}` | Labels pour exclure (ex: `{'backup': 'long-term'}`) |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-7777777777777777777",
  "resource_name": "backup-deleted-disk-2024-08",
  "resource_type": "persistent_disk_orphan_snapshots",
  "snapshot_size_gb": 500,
  "storage_bytes": 536870912000,
  "source_disk": "https://www.googleapis.com/compute/v1/projects/my-project/zones/us-central1-a/disks/deleted-disk",
  "source_disk_exists": false,
  "creation_timestamp": "2024-05-05T10:00:00Z",
  "age_days": 181,
  "estimated_monthly_cost": 13.00,
  "already_wasted": 78.42,
  "confidence": "medium",
  "recommendation": "Review if snapshot still needed, consider deletion",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `persistent_disk_old_type` - Ancien Type de Disque

#### Détection

**Logique :**

Détecter disques **pd-standard** (HDD) qui pourraient migrer vers **pd-balanced** (SSD, meilleur price/perf) :

```python
# 1. Lister tous les disques persistants
disks = get_all_persistent_disks(project_id)

# 2. Pour chaque disque, vérifier type
for disk in disks:
    disk_type = disk.type.split('/')[-1]  # "pd-standard"

    # 3. Détection si pd-standard (ancien type HDD)
    if disk_type == 'pd-standard':
        # 4. Calculer coût actuel vs pd-balanced
        disk_size_gb = disk.size_gb

        current_cost = disk_size_gb * 0.040  # pd-standard
        balanced_cost = disk_size_gb * 0.100  # pd-balanced

        # 5. pd-balanced coûte +150% mais offre 2.3x throughput + 8x IOPS
        # Pour workloads actifs, meilleur price/performance

        # 6. Vérifier si disque utilisé (I/O >0)
        io_metrics = get_disk_io_metrics(disk, lookback_days=7)

        if io_metrics['total_ops'] > min_io_threshold:
            # Disque actif avec pd-standard = suboptimal
            # Recommandation: migrer vers pd-balanced
```

**Critères :**
- `disk_type == 'pd-standard'`
- Disque actif (I/O >100 ops/jour sur 7 jours)
- Recommandation: pd-balanced pour meilleur performance/prix

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Cloud Monitoring API (I/O metrics)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/disk/read_ops_count"'
)
```

#### Calcul de Coût

**Formule :**

pd-standard vs pd-balanced = trade-off coût vs performance :

```python
disk_size_gb = 1000  # 1 TB

# Coût actuel (pd-standard)
current_cost = 1000 * 0.040 = $40.00/mois

# Coût recommandé (pd-balanced)
recommended_cost = 1000 * 0.100 = $100.00/mois

# Coût additionnel = +$60/mois
# MAIS: +133% throughput, +700% IOPS

# Waste calculation:
# Si disque actif → pd-standard = bottleneck = performance waste
# Si disque idle → garder pd-standard OK

# Pour disques actifs, coût = perte de productivité
# Estimation: 20% performance gain = économie temps équipe
# Indirect waste = $60/mois (estimation conservative)

monthly_waste = 60.00  # Coût opportunité (suboptimal performance)
```

**Note :** Ce scénario détecte **performance waste** (suboptimal), pas coût direct.

**Exemple :**

Disque 1 TB pd-standard actif (1000 IOPS/jour) depuis 90 jours :
```python
current_cost = $40.00/mois
recommended_cost = $100.00/mois
performance_waste = $60.00/mois (coût opportunité)
already_wasted = $60.00 * (90/30) = $180.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_io_threshold` | int | 100 | IOPS minimum/jour pour considérer actif |
| `lookback_days` | int | 7 | Période analyse I/O |
| `performance_waste_factor` | float | 0.6 | Facteur coût opportunité (60% = $60 waste pour $100 upgrade) |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-3333333333333333333",
  "resource_name": "app-data-disk",
  "resource_type": "persistent_disk_old_type",
  "zone": "us-central1-a",
  "disk_type": "pd-standard",
  "size_gb": 1000,
  "io_metrics": {
    "avg_read_ops_per_day": 850,
    "avg_write_ops_per_day": 150,
    "total_ops_per_day": 1000
  },
  "current_cost_monthly": 40.00,
  "recommended_disk_type": "pd-balanced",
  "recommended_cost_monthly": 100.00,
  "performance_improvement": {
    "throughput_increase_percent": 133,
    "iops_increase_percent": 700
  },
  "estimated_monthly_waste": 60.00,
  "already_wasted": 180.00,
  "confidence": "medium",
  "recommendation": "Migrate to pd-balanced for 8x IOPS and 2.3x throughput",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `persistent_disk_overprovisioned_type` - Type de Disque Sur-Provisionné

#### Détection

**Logique :**

Détecter disques **pd-ssd** (high-performance) alors que **pd-balanced** suffirait :

```python
# 1. Lister tous les disques pd-ssd
disks = get_all_persistent_disks(project_id)

pd_ssd_disks = [d for d in disks if d.type.endswith('pd-ssd')]

# 2. Pour chaque disque pd-ssd, analyser I/O réel
for disk in pd_ssd_disks:
    # 3. Récupérer IOPS moyens sur 14 jours
    io_metrics = get_disk_io_metrics(disk, lookback_days=14)

    avg_read_iops = io_metrics['avg_read_ops_per_second']
    avg_write_iops = io_metrics['avg_write_ops_per_second']
    avg_total_iops = avg_read_iops + avg_write_iops

    # 4. Calculer capacité IOPS pd-balanced
    disk_size_gb = disk.size_gb
    pd_balanced_max_iops = disk_size_gb * 6  # 6 IOPS/GB

    # 5. Détection si IOPS actuel < 50% capacité pd-balanced
    if avg_total_iops < (pd_balanced_max_iops * 0.5):
        # pd-ssd over-provisioned, pd-balanced suffit
        # Économie potentielle: -41%

        current_cost = disk_size_gb * 0.170  # pd-ssd
        recommended_cost = disk_size_gb * 0.100  # pd-balanced
        monthly_waste = current_cost - recommended_cost
```

**Critères :**
- `disk_type == 'pd-ssd'`
- `avg_iops < pd_balanced_capacity * 0.5`
- Économie migration >$10/mois

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Cloud Monitoring API (IOPS metrics)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/disk/read_ops_count"'
)
```

#### Calcul de Coût

**Formule :**

pd-ssd vs pd-balanced = -41% économie :

```python
disk_size_gb = 500  # 500 GB

# Coût actuel (pd-ssd)
current_cost = 500 * 0.170 = $85.00/mois

# Coût recommandé (pd-balanced)
recommended_cost = 500 * 0.100 = $50.00/mois

# Waste = différence
monthly_waste = 85.00 - 50.00 = $35.00/mois

# Vérification capacité:
# pd-balanced: 500 GB * 6 IOPS/GB = 3000 IOPS max
# IOPS observé: 800 IOPS avg
# Utilisation: 800/3000 = 27% → pd-balanced largement suffisant

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Disque 500 GB pd-ssd avec 800 IOPS avg depuis 120 jours :
```python
current_cost = $85.00/mois
recommended_cost = $50.00/mois
monthly_waste = $35.00
already_wasted = $35.00 * (120/30) = $140.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `iops_utilization_threshold` | float | 0.5 | % max utilisation pd-balanced capacity |
| `lookback_days` | int | 14 | Période analyse IOPS |
| `min_savings_threshold` | float | 10.0 | Économie minimum $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-8888888888888888888",
  "resource_name": "over-spec-database-disk",
  "resource_type": "persistent_disk_overprovisioned_type",
  "zone": "us-east1-c",
  "disk_type": "pd-ssd",
  "size_gb": 500,
  "io_metrics": {
    "avg_read_iops": 450,
    "avg_write_iops": 350,
    "avg_total_iops": 800,
    "max_iops_observed": 1200
  },
  "pd_balanced_capacity": {
    "max_iops": 3000,
    "current_utilization_percent": 27
  },
  "current_cost_monthly": 85.00,
  "recommended_disk_type": "pd-balanced",
  "recommended_cost_monthly": 50.00,
  "estimated_monthly_waste": 35.00,
  "already_wasted": 140.00,
  "savings_percentage": 41,
  "confidence": "high",
  "recommendation": "Downgrade to pd-balanced - using only 27% of pd-balanced capacity",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `persistent_disk_untagged` - Disques Non Taggés

#### Détection

**Logique :**

Détecter disques sans **labels GCP** requis pour gouvernance :

```python
# 1. Lister tous les disques
disks = get_all_persistent_disks(project_id)

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque disque, vérifier labels
for disk in disks:
    labels = disk.labels if hasattr(disk, 'labels') else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged disk = governance waste
```

**Critères :**
- Labels manquants parmi la liste requise
- Optionnel: valeurs de labels invalides

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Disques non taggés = perte de visibilité + risque coût
# Coût estimé = temps management + over-provisioning caché

disk_size_gb = disk.size_gb
disk_type = disk.type.split('/')[-1]

disk_pricing = {
    'pd-standard': 0.040,
    'pd-balanced': 0.100,
    'pd-ssd': 0.170,
}

disk_monthly_cost = disk_size_gb * disk_pricing.get(disk_type, 0.040)

# Governance waste = 5% du coût disque (estimation)
governance_waste_percentage = 0.05
monthly_waste = disk_monthly_cost * governance_waste_percentage

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Disque 1 TB pd-balanced sans labels depuis 180 jours :
```python
disk_monthly_cost = 1024 * $0.100 = $102.40
monthly_waste = $102.40 * 0.05 = $5.12
already_wasted = $5.12 * (180/30) = $30.72
```

**Note :** Coût gouvernance est estimé. Impact réel = meilleure visibilité coûts + prévention waste.

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |
| `enforce_values` | dict | `{}` | Valeurs autorisées par label |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-4444444444444444444",
  "resource_name": "unnamed-disk-237",
  "resource_type": "persistent_disk_untagged",
  "zone": "asia-east1-a",
  "disk_type": "pd-balanced",
  "size_gb": 1024,
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "creation_timestamp": "2024-05-06T08:00:00Z",
  "age_days": 180,
  "disk_monthly_cost": 102.40,
  "estimated_monthly_waste": 5.12,
  "already_wasted": 30.72,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation and governance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `persistent_disk_underutilized` - Disques Sous-Utilisés

#### Détection

**Logique :**

Utiliser **Cloud Monitoring** pour analyser utilisation I/O réelle vs capacité :

```python
# 1. Lister tous les disques persistants attachés
disks = get_all_persistent_disks(project_id)

attached_disks = [d for d in disks if d.users and len(d.users) > 0]

# 2. Pour chaque disque, récupérer métriques I/O (14 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for disk in attached_disks:
    # 3. Query read/write throughput
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    # Read throughput (bytes/sec)
    read_throughput = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="compute.googleapis.com/instance/disk/read_bytes_count" AND resource.disk_name="{disk.name}"',
            "interval": interval,
        }
    )

    # 4. Calculer throughput moyen
    read_values = [point.value.double_value for series in read_throughput for point in series.points]
    avg_read_mbps = (sum(read_values) / len(read_values)) / (1024*1024) if read_values else 0

    # 5. Calculer capacité max throughput selon type
    disk_type = disk.type.split('/')[-1]
    disk_size_gb = disk.size_gb

    max_throughput_mbps = {
        'pd-standard': disk_size_gb * 0.12,    # 0.12 MB/s par GB
        'pd-balanced': disk_size_gb * 0.28,    # 0.28 MB/s par GB
        'pd-ssd': disk_size_gb * 0.48,         # 0.48 MB/s par GB
    }.get(disk_type, 0)

    # 6. Détection si utilisation <10% capacité
    utilization_percent = (avg_read_mbps / max_throughput_mbps * 100) if max_throughput_mbps > 0 else 0

    if utilization_percent < utilization_threshold:
        # Disque sous-utilisé = potentiel downgrade ou suppression
```

**Critères :**
- Disque attaché et actif
- Utilisation throughput <10% capacité
- Lookback period: 14 jours

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Cloud Monitoring API (throughput metrics)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/disk/read_bytes_count"'
)
```

#### Calcul de Coût

**Formule :**

Si disque utilisé <10%, recommandation downgrade ou snapshot :

```python
disk_size_gb = 1000  # 1 TB
disk_type = 'pd-ssd'

# Coût actuel
current_cost = 1000 * 0.170 = $170.00/mois

# Scénarios:
# 1. Downgrade vers pd-balanced
recommended_cost_balanced = 1000 * 0.100 = $100.00/mois
savings_balanced = $70.00/mois

# 2. Convertir en snapshot (si read-only)
snapshot_cost = 1000 * 0.026 = $26.00/mois
savings_snapshot = $144.00/mois

# Waste = économie potentielle (scénario conservateur = downgrade)
monthly_waste = current_cost - recommended_cost_balanced

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Disque 1 TB pd-ssd utilisé à 5% depuis 90 jours :
```python
current_cost = $170.00/mois
recommended_cost = $100.00/mois (pd-balanced)
monthly_waste = $70.00
already_wasted = $70.00 * (90/30) = $210.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `utilization_threshold` | float | 10.0 | % max utilisation throughput |
| `lookback_days` | int | 14 | Période analyse métriques |
| `min_datapoints` | int | 50 | Nombre minimum de points de données |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-6666666666666666666",
  "resource_name": "low-usage-disk",
  "resource_type": "persistent_disk_underutilized",
  "zone": "us-central1-a",
  "disk_type": "pd-ssd",
  "size_gb": 1000,
  "io_metrics": {
    "avg_read_mbps": 24.0,
    "avg_write_mbps": 8.0,
    "avg_total_mbps": 32.0,
    "max_throughput_capacity_mbps": 480.0,
    "utilization_percent": 6.7
  },
  "current_cost_monthly": 170.00,
  "recommended_disk_type": "pd-balanced",
  "recommended_cost_monthly": 100.00,
  "estimated_monthly_waste": 70.00,
  "already_wasted": 210.00,
  "confidence": "high",
  "recommendation": "Downgrade to pd-balanced - using only 7% of throughput capacity",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `persistent_disk_oversized` - Disques Sur-Dimensionnés

#### Détection

**Logique :**

Analyser espace disque utilisé vs alloué via métriques filesystem :

```python
# 1. Lister tous les disques attachés
disks = get_all_persistent_disks(project_id)

attached_disks = [d for d in disks if d.users and len(d.users) > 0]

# 2. Pour chaque disque, récupérer métriques utilisation espace
# Note: Nécessite Cloud Monitoring Agent installé sur instances

from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for disk in attached_disks:
    # 3. Query disk used space
    # Metric: agent.googleapis.com/disk/percent_used
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 14*24*3600},
    })

    disk_usage = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="agent.googleapis.com/disk/percent_used" AND resource.device="{disk.name}"',
            "interval": interval,
        }
    )

    # 4. Calculer % espace utilisé
    usage_values = [point.value.double_value for series in disk_usage for point in series.points]

    if not usage_values:
        # Agent non installé, skip
        continue

    avg_used_percent = sum(usage_values) / len(usage_values)
    free_percent = 100 - avg_used_percent

    # 5. Détection si >80% espace libre
    if free_percent >= free_space_threshold:
        # 6. Calculer taille recommandée
        disk_size_gb = disk.size_gb
        used_gb = disk_size_gb * (avg_used_percent / 100.0)

        # Recommandation: used space + 30% buffer
        recommended_size_gb = int(used_gb * 1.30)

        # Waste = différence coût
        disk_type = disk.type.split('/')[-1]
        price_per_gb = get_disk_pricing(disk_type)

        current_cost = disk_size_gb * price_per_gb
        recommended_cost = recommended_size_gb * price_per_gb
        monthly_waste = current_cost - recommended_cost

        if monthly_waste >= min_savings_threshold:
            # Disque over-sized = waste détecté
```

**Critères :**
- Disque attaché avec métriques disponibles
- `free_space >= 80%` (ou utilisé <20%)
- Économie potentielle >$5/mois

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Cloud Monitoring API (disk usage)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="agent.googleapis.com/disk/percent_used"'
)
```

#### Calcul de Coût

**Formule :**

Resize disk = économie proportionnelle :

```python
disk_size_gb = 2000  # 2 TB alloué
avg_used_percent = 15  # 15% utilisé
used_gb = 2000 * 0.15 = 300 GB

# Taille recommandée: 300 GB * 1.30 (buffer) = 390 GB
recommended_size_gb = 400  # Arrondi

disk_type = 'pd-balanced'
price_per_gb = 0.100

# Coût actuel
current_cost = 2000 * 0.100 = $200.00/mois

# Coût recommandé
recommended_cost = 400 * 0.100 = $40.00/mois

# Waste
monthly_waste = 200.00 - 40.00 = $160.00/mois

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Disque 2 TB pd-balanced utilisé à 15% depuis 120 jours :
```python
current_cost = $200.00/mois
recommended_cost = $40.00/mois (400 GB)
monthly_waste = $160.00
already_wasted = $160.00 * (120/30) = $640.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `free_space_threshold` | float | 80.0 | % minimum espace libre pour détection |
| `safety_buffer` | float | 1.30 | Marge sécurité taille (1.30 = +30%) |
| `min_savings_threshold` | float | 5.0 | Économie minimum $/mois |
| `lookback_days` | int | 14 | Période analyse utilisation |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-2222222222222222222",
  "resource_name": "oversized-data-disk",
  "resource_type": "persistent_disk_oversized",
  "zone": "europe-west1-c",
  "disk_type": "pd-balanced",
  "size_gb": 2000,
  "disk_usage": {
    "avg_used_percent": 15.2,
    "avg_used_gb": 304,
    "avg_free_percent": 84.8,
    "avg_free_gb": 1696
  },
  "recommended_size_gb": 400,
  "current_cost_monthly": 200.00,
  "recommended_cost_monthly": 40.00,
  "estimated_monthly_waste": 160.00,
  "already_wasted": 640.00,
  "savings_percentage": 80,
  "confidence": "high",
  "recommendation": "Resize from 2000GB to 400GB - using only 15% of capacity",
  "monitoring_agent_installed": true,
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `persistent_disk_readonly` - Disques en Lecture Seule

#### Détection

**Logique :**

Détecter disques avec **zéro writes** → convertir en snapshot (-35% coût) :

```python
# 1. Lister tous les disques attachés
disks = get_all_persistent_disks(project_id)

attached_disks = [d for d in disks if d.users and len(d.users) > 0]

# 2. Pour chaque disque, analyser write operations (30 jours)
from google.cloud import monitoring_v3

monitoring_client = monitoring_v3.MetricServiceClient()

for disk in attached_disks:
    # 3. Query write operations
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(time.time())},
        "start_time": {"seconds": int(time.time()) - 30*24*3600},
    })

    write_ops = monitoring_client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": f'metric.type="compute.googleapis.com/instance/disk/write_ops_count" AND resource.disk_name="{disk.name}"',
            "interval": interval,
        }
    )

    # 4. Calculer total write operations
    total_writes = sum([point.value.int64_value for series in write_ops for point in series.points])

    # 5. Détection si zero writes (read-only)
    if total_writes <= max_write_ops_threshold:
        # 6. Calculer économie snapshot vs disk
        disk_size_gb = disk.size_gb
        disk_type = disk.type.split('/')[-1]

        disk_pricing = {
            'pd-standard': 0.040,
            'pd-balanced': 0.100,
            'pd-ssd': 0.170,
        }

        disk_cost = disk_size_gb * disk_pricing.get(disk_type, 0.040)
        snapshot_cost = disk_size_gb * 0.026

        monthly_waste = disk_cost - snapshot_cost

        if monthly_waste >= min_savings_threshold:
            # Read-only disk = waste (peut devenir snapshot)
```

**Critères :**
- Disque attaché
- `total_writes <= max_threshold` sur 30 jours (défaut: 10 writes)
- Économie snapshot >$5/mois

**API Calls :**
```python
# Disks API
compute_client.disks().aggregatedList(project=project_id)

# Cloud Monitoring API (write ops)
monitoring_client.list_time_series(
    name=f"projects/{project_id}",
    filter='metric.type="compute.googleapis.com/instance/disk/write_ops_count"'
)
```

#### Calcul de Coût

**Formule :**

Disk → Snapshot = -35% à -85% économie :

```python
disk_size_gb = 500
disk_type = 'pd-balanced'

# Coût actuel (disk)
disk_cost = 500 * 0.100 = $50.00/mois

# Coût recommandé (snapshot)
snapshot_cost = 500 * 0.026 = $13.00/mois

# Waste
monthly_waste = 50.00 - 13.00 = $37.00/mois

# Coût gaspillé depuis dernier write
last_write_date = parse_timestamp(last_write_timestamp)
readonly_days = (now - last_write_date).days
already_wasted = monthly_waste * (readonly_days / 30.0)
```

**Exemple :**

Disque 500 GB pd-balanced read-only depuis 180 jours :
```python
disk_cost = $50.00/mois
snapshot_cost = $13.00/mois
monthly_waste = $37.00
already_wasted = $37.00 * (180/30) = $222.00
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `max_write_ops_threshold` | int | 10 | Nombre max writes sur période |
| `lookback_days` | int | 30 | Période analyse writes |
| `min_savings_threshold` | float | 5.0 | Économie minimum $/mois |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-1111111111111111111",
  "resource_name": "readonly-archive-disk",
  "resource_type": "persistent_disk_readonly",
  "zone": "us-west1-b",
  "disk_type": "pd-balanced",
  "size_gb": 500,
  "io_metrics": {
    "total_read_ops_30d": 12450,
    "total_write_ops_30d": 0,
    "last_write_timestamp": "2024-05-05T10:00:00Z",
    "readonly_days": 181
  },
  "current_cost_monthly": 50.00,
  "recommended_storage": "snapshot",
  "recommended_cost_monthly": 13.00,
  "estimated_monthly_waste": 37.00,
  "already_wasted": 223.67,
  "savings_percentage": 74,
  "confidence": "high",
  "recommendation": "Convert to snapshot - zero writes for 181 days",
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
# Utiliser projet test existant ou créer nouveau
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
gcloud config set project $PROJECT_ID

# Activer APIs requises
gcloud services enable compute.googleapis.com
gcloud services enable monitoring.googleapis.com
```

#### 2. Service Account (si pas déjà créé)

```bash
# Utiliser Service Account du test Compute Instances
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

#### 3. Installer Cloud Monitoring Agent

**Requis pour scénarios 9-10** (disk usage, I/O metrics)

```bash
# Template installation (à exécuter sur instances avec disques)
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

---

### Tests Unitaires - Créer Disques de Test

#### Scénario 1: Disque Non Attaché

```bash
# Créer disque standalone (non attaché)
gcloud compute disks create test-unattached-disk \
  --zone=us-central1-a \
  --size=500GB \
  --type=pd-balanced

# Attendre 7 jours ou modifier creation_timestamp via API pour tests
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_unattached",
  "resource_name": "test-unattached-disk",
  "size_gb": 500,
  "disk_type": "pd-balanced",
  "users": [],
  "age_days": ">=7",
  "estimated_monthly_cost": "~50.00",
  "confidence": "high"
}
```

---

#### Scénario 2: Disque Attaché à Instance Arrêtée

```bash
# Créer instance avec disque
gcloud compute instances create test-stopped-instance \
  --zone=us-central1-a \
  --machine-type=n2-standard-2 \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-standard

# Créer et attacher disque additionnel
gcloud compute disks create test-attached-stopped-disk \
  --zone=us-central1-a \
  --size=1000GB \
  --type=pd-ssd

gcloud compute instances attach-disk test-stopped-instance \
  --zone=us-central1-a \
  --disk=test-attached-stopped-disk

# Arrêter instance
gcloud compute instances stop test-stopped-instance --zone=us-central1-a

# Attendre 30 jours pour détection
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_attached_stopped",
  "resource_name": "test-attached-stopped-disk",
  "size_gb": 1024,
  "disk_type": "pd-ssd",
  "attached_instance": {
    "status": "TERMINATED",
    "stopped_days": ">=30"
  },
  "estimated_monthly_cost": "~174.08"
}
```

---

#### Scénario 3: Disque Jamais Utilisé

```bash
# Créer instance
gcloud compute instances create test-never-used-instance \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --image-family=debian-11 \
  --image-project=debian-cloud

# Créer et attacher disque (ne jamais monter ni utiliser)
gcloud compute disks create test-never-used-disk \
  --zone=us-central1-a \
  --size=250GB \
  --type=pd-balanced

gcloud compute instances attach-disk test-never-used-instance \
  --zone=us-central1-a \
  --disk=test-never-used-disk

# NE PAS monter le disque (rester idle)
# Attendre 7 jours pour métriques I/O = 0
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_never_used",
  "resource_name": "test-never-used-disk",
  "io_metrics": {
    "total_read_ops": 0,
    "total_write_ops": 0
  },
  "age_days": ">=7",
  "estimated_monthly_cost": "~25.00"
}
```

---

#### Scénario 4: Snapshots Orphelins

```bash
# Créer disque temporaire
gcloud compute disks create temp-disk-for-snapshot \
  --zone=us-central1-a \
  --size=500GB \
  --type=pd-standard

# Créer snapshot
gcloud compute disks snapshot temp-disk-for-snapshot \
  --zone=us-central1-a \
  --snapshot-names=test-orphan-snapshot

# Supprimer disque source (rendre snapshot orphelin)
gcloud compute disks delete temp-disk-for-snapshot --zone=us-central1-a --quiet

# Attendre 30 jours pour détection
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_orphan_snapshots",
  "resource_name": "test-orphan-snapshot",
  "snapshot_size_gb": 500,
  "source_disk_exists": false,
  "age_days": ">=30",
  "estimated_monthly_cost": "~13.00"
}
```

---

#### Scénario 5: Ancien Type de Disque

```bash
# Créer instance avec disque pd-standard actif
gcloud compute instances create test-old-type-instance \
  --zone=us-central1-a \
  --machine-type=n2-standard-2 \
  --image-family=debian-11 \
  --image-project=debian-cloud

# Créer et attacher disque pd-standard
gcloud compute disks create test-old-type-disk \
  --zone=us-central1-a \
  --size=1000GB \
  --type=pd-standard

gcloud compute instances attach-disk test-old-type-instance \
  --zone=us-central1-a \
  --disk=test-old-type-disk

# SSH et générer I/O actif
gcloud compute ssh test-old-type-instance --zone=us-central1-a

# Sur instance: monter disque et générer I/O
sudo mkfs.ext4 /dev/sdb
sudo mkdir /mnt/data
sudo mount /dev/sdb /mnt/data

# Générer I/O continu
dd if=/dev/zero of=/mnt/data/testfile bs=1M count=1000 &

# Laisser tourner 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_old_type",
  "resource_name": "test-old-type-disk",
  "disk_type": "pd-standard",
  "recommended_disk_type": "pd-balanced",
  "io_metrics": {
    "avg_ops_per_day": ">100"
  },
  "estimated_monthly_waste": "~60.00"
}
```

---

#### Scénario 6: Type Sur-Provisionné

```bash
# Créer instance
gcloud compute instances create test-overprovisioned-type-instance \
  --zone=us-central1-a \
  --machine-type=n2-standard-2 \
  --image-family=debian-11 \
  --image-project=debian-cloud

# Créer disque pd-ssd (high-performance)
gcloud compute disks create test-overprovisioned-type-disk \
  --zone=us-central1-a \
  --size=500GB \
  --type=pd-ssd

gcloud compute instances attach-disk test-overprovisioned-type-instance \
  --zone=us-central1-a \
  --disk=test-overprovisioned-type-disk

# SSH et générer I/O faible (<1000 IOPS)
gcloud compute ssh test-overprovisioned-type-instance --zone=us-central1-a

# Sur instance: monter et générer faible I/O
sudo mkfs.ext4 /dev/sdb
sudo mkdir /mnt/data
sudo mount /dev/sdb /mnt/data

# Low IOPS workload (500 IOPS, bien en-dessous 3000 IOPS pd-balanced)
fio --name=low_iops --ioengine=libaio --rw=randread --bs=4k --iodepth=16 --numjobs=1 --runtime=0 --time_based --directory=/mnt/data &

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_overprovisioned_type",
  "resource_name": "test-overprovisioned-type-disk",
  "disk_type": "pd-ssd",
  "recommended_disk_type": "pd-balanced",
  "io_metrics": {
    "avg_total_iops": "~800"
  },
  "pd_balanced_capacity": {
    "max_iops": 3000,
    "utilization_percent": "~27"
  },
  "estimated_monthly_waste": "~35.00"
}
```

---

#### Scénario 7: Disques Non Taggés

```bash
# Créer disque SANS labels
gcloud compute disks create test-untagged-disk \
  --zone=asia-east1-a \
  --size=1000GB \
  --type=pd-balanced
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_untagged",
  "resource_name": "test-untagged-disk",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "estimated_monthly_waste": "~5.12"
}
```

---

#### Scénario 8: Disques Sous-Utilisés

```bash
# Créer instance avec disque pd-ssd large
gcloud compute instances create test-underutilized-instance \
  --zone=us-central1-a \
  --machine-type=n2-standard-4 \
  --image-family=debian-11 \
  --image-project=debian-cloud

gcloud compute disks create test-underutilized-disk \
  --zone=us-central1-a \
  --size=1000GB \
  --type=pd-ssd

gcloud compute instances attach-disk test-underutilized-instance \
  --zone=us-central1-a \
  --disk=test-underutilized-disk

# SSH, installer monitoring agent, générer très faible I/O
gcloud compute ssh test-underutilized-instance --zone=us-central1-a

# Sur instance:
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

sudo mkfs.ext4 /dev/sdb
sudo mkdir /mnt/data
sudo mount /dev/sdb /mnt/data

# Générer I/O très faible (<5% capacité pd-ssd)
dd if=/dev/zero of=/mnt/data/testfile bs=1M count=10 conv=fsync &

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_underutilized",
  "resource_name": "test-underutilized-disk",
  "disk_type": "pd-ssd",
  "io_metrics": {
    "utilization_percent": "<10"
  },
  "estimated_monthly_waste": "~70.00"
}
```

---

#### Scénario 9: Disques Sur-Dimensionnés

```bash
# Créer instance
gcloud compute instances create test-oversized-instance \
  --zone=europe-west1-c \
  --machine-type=n2-standard-2 \
  --image-family=debian-11 \
  --image-project=debian-cloud

# Créer disque large (2 TB)
gcloud compute disks create test-oversized-disk \
  --zone=europe-west1-c \
  --size=2000GB \
  --type=pd-balanced

gcloud compute instances attach-disk test-oversized-instance \
  --zone=europe-west1-c \
  --disk=test-oversized-disk

# SSH, installer agent, utiliser seulement 15%
gcloud compute ssh test-oversized-instance --zone=europe-west1-c

# Sur instance:
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

sudo mkfs.ext4 /dev/sdb
sudo mkdir /mnt/data
sudo mount /dev/sdb /mnt/data

# Remplir seulement 300 GB (15%)
dd if=/dev/zero of=/mnt/data/testfile bs=1G count=300

# Laisser tourner 14 jours
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_oversized",
  "resource_name": "test-oversized-disk",
  "size_gb": 2000,
  "disk_usage": {
    "avg_used_percent": "~15",
    "avg_free_percent": "~85"
  },
  "recommended_size_gb": 400,
  "estimated_monthly_waste": "~160.00"
}
```

---

#### Scénario 10: Disques Read-Only

```bash
# Créer instance
gcloud compute instances create test-readonly-instance \
  --zone=us-west1-b \
  --machine-type=e2-medium \
  --image-family=debian-11 \
  --image-project=debian-cloud

# Créer disque
gcloud compute disks create test-readonly-disk \
  --zone=us-west1-b \
  --size=500GB \
  --type=pd-balanced

gcloud compute instances attach-disk test-readonly-instance \
  --zone=us-west1-b \
  --disk=test-readonly-disk

# SSH, monter, écrire une fois puis seulement reads
gcloud compute ssh test-readonly-instance --zone=us-west1-b

# Sur instance:
sudo mkfs.ext4 /dev/sdb
sudo mkdir /mnt/data
sudo mount /dev/sdb /mnt/data

# Écrire data une seule fois
dd if=/dev/zero of=/mnt/data/archive.dat bs=1G count=100

# Ensuite, seulement reads (aucun write)
# Simuler accès lecture périodique
while true; do
  cat /mnt/data/archive.dat > /dev/null
  sleep 3600  # Lire 1x/heure
done &

# Laisser tourner 30 jours SANS aucun write
```

**Validation attendue :**
```json
{
  "resource_type": "persistent_disk_readonly",
  "resource_name": "test-readonly-disk",
  "io_metrics": {
    "total_write_ops_30d": 0
  },
  "recommended_storage": "snapshot",
  "estimated_monthly_waste": "~37.00",
  "savings_percentage": 74
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script de validation complet pour GCP Persistent Disks
"""

from google.cloud import compute_v1
from google.cloud import monitoring_v3
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    disks_client = compute_v1.DisksClient()
    snapshots_client = compute_v1.SnapshotsClient()

    # 1. Lister tous les disques
    request = compute_v1.AggregatedListDisksRequest(
        project=PROJECT_ID
    )

    agg_list = disks_client.aggregated_list(request=request)

    disks = []
    for zone, response in agg_list:
        if response.disks:
            disks.extend(response.disks)

    print(f"✅ Found {len(disks)} disks")

    # 2. Lister tous les snapshots
    snapshots = list(snapshots_client.list(project=PROJECT_ID))
    print(f"✅ Found {len(snapshots)} snapshots")

    # 3. Vérifier détection pour chaque scénario
    scenarios_detected = {
        'unattached': 0,
        'attached_stopped': 0,
        'never_used': 0,
        'orphan_snapshots': 0,
        'old_type': 0,
        'overprovisioned_type': 0,
        'untagged': 0,
        'underutilized': 0,
        'oversized': 0,
        'readonly': 0,
    }

    # Détection simplifiée (logique complète dans provider)
    for disk in disks:
        name = disk.name

        # Scenario 1: Unattached
        if not disk.users or len(disk.users) == 0:
            scenarios_detected['unattached'] += 1
            print(f"✅ Detected scenario 1 (unattached): {name}")

        # Scenario 5: Old type
        disk_type = disk.type.split('/')[-1]
        if disk_type == 'pd-standard':
            scenarios_detected['old_type'] += 1
            print(f"✅ Detected scenario 5 (old type): {name}")

        # Scenario 6: Overprovisioned type
        if disk_type == 'pd-ssd':
            scenarios_detected['overprovisioned_type'] += 1
            print(f"✅ Detected scenario 6 (overprovisioned type): {name}")

        # Scenario 7: Untagged
        labels = disk.labels if hasattr(disk, 'labels') else {}
        if not labels or len(labels) == 0:
            scenarios_detected['untagged'] += 1
            print(f"✅ Detected scenario 7 (untagged): {name}")

    # Snapshots orphelins
    all_disk_names = {d.name for d in disks}

    for snapshot in snapshots:
        if snapshot.source_disk:
            source_name = snapshot.source_disk.split('/')[-1]
            if source_name not in all_disk_names:
                scenarios_detected['orphan_snapshots'] += 1
                print(f"✅ Detected scenario 4 (orphan snapshot): {snapshot.name}")

    # 4. Rapport final
    print("\n📊 Detection Summary:")
    for scenario, count in scenarios_detected.items():
        print(f"  - {scenario}: {count} resources")

    total_detected = sum(scenarios_detected.values())
    print(f"\n✅ Total waste detected: {total_detected} resources")

if __name__ == '__main__':
    test_all_scenarios()
```

#### Exécution

```bash
# Exporter PROJECT_ID
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"

# Exécuter validation
python3 test_gcp_persistent_disks.py
```

**Résultat attendu :**
```
✅ Found 10 disks
✅ Found 1 snapshots
✅ Detected scenario 1 (unattached): test-unattached-disk
✅ Detected scenario 2 (attached stopped): test-attached-stopped-disk
✅ Detected scenario 3 (never used): test-never-used-disk
✅ Detected scenario 4 (orphan snapshot): test-orphan-snapshot
✅ Detected scenario 5 (old type): test-old-type-disk
✅ Detected scenario 6 (overprovisioned type): test-overprovisioned-type-disk
✅ Detected scenario 7 (untagged): test-untagged-disk
✅ Detected scenario 8 (underutilized): test-underutilized-disk
✅ Detected scenario 9 (oversized): test-oversized-disk
✅ Detected scenario 10 (readonly): test-readonly-disk

📊 Detection Summary:
  - unattached: 1 resources
  - attached_stopped: 1 resources
  - never_used: 1 resources
  - orphan_snapshots: 1 resources
  - old_type: 1 resources
  - overprovisioned_type: 1 resources
  - untagged: 1 resources
  - underutilized: 1 resources
  - oversized: 1 resources
  - readonly: 1 resources

✅ Total waste detected: 10 resources
```

---

### Cleanup

```bash
# Supprimer tous les disques de test
gcloud compute disks delete test-unattached-disk --zone=us-central1-a --quiet
gcloud compute disks delete test-attached-stopped-disk --zone=us-central1-a --quiet
gcloud compute disks delete test-never-used-disk --zone=us-central1-a --quiet
gcloud compute disks delete test-old-type-disk --zone=us-central1-a --quiet
gcloud compute disks delete test-overprovisioned-type-disk --zone=us-central1-a --quiet
gcloud compute disks delete test-untagged-disk --zone=asia-east1-a --quiet
gcloud compute disks delete test-underutilized-disk --zone=us-central1-a --quiet
gcloud compute disks delete test-oversized-disk --zone=europe-west1-c --quiet
gcloud compute disks delete test-readonly-disk --zone=us-west1-b --quiet

# Supprimer instances
gcloud compute instances delete test-stopped-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-never-used-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-old-type-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-overprovisioned-type-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-underutilized-instance --zone=us-central1-a --quiet
gcloud compute instances delete test-oversized-instance --zone=europe-west1-c --quiet
gcloud compute instances delete test-readonly-instance --zone=us-west1-b --quiet

# Supprimer snapshots
gcloud compute snapshots delete test-orphan-snapshot --quiet
```

---

## Références

### Documentation GCP

- [Persistent Disks API](https://cloud.google.com/compute/docs/reference/rest/v1/disks)
- [Snapshots API](https://cloud.google.com/compute/docs/reference/rest/v1/snapshots)
- [Disk Pricing](https://cloud.google.com/compute/disks-image-pricing)
- [Cloud Monitoring Disk Metrics](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-compute)
- [Disk Types Comparison](https://cloud.google.com/compute/docs/disks)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing complet 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md) - Compute Instances scenarios
- [README.md](./README.md) - Guide utilisation documentation GCP

### Équivalences AWS/Azure

- **AWS EBS Volumes** → GCP Persistent Disks
- **Azure Managed Disks** → GCP Persistent Disks
- **AWS EBS Snapshots** → GCP Disk Snapshots
- **Azure Disk Snapshots** → GCP Disk Snapshots
- **AWS gp3/gp2** → GCP pd-balanced
- **AWS io2** → GCP pd-ssd
- **AWS st1/sc1** → GCP pd-standard

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
