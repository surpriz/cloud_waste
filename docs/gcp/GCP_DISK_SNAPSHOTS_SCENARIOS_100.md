# CloudWaste - Couverture 100% GCP Disk Snapshots

**Resource Type:** `Compute : Disk Snapshots`
**Provider:** Google Cloud Platform (GCP)
**API:** `compute.googleapis.com` (Compute Engine API v1)
**Équivalents:** AWS EBS Snapshots, Azure Disk Snapshots
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing Disk Snapshots](#modèle-de-pricing-disk-snapshots)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Snapshots Orphelins](#1-disk_snapshot_orphaned---snapshots-orphelins)
  - [2. Snapshots Redondants](#2-disk_snapshot_redundant---snapshots-redondants)
  - [3. Snapshots Vieux Jamais Restaurés](#3-disk_snapshot_old_unused---snapshots-vieux-jamais-restaurés)
  - [4. Sans Politique de Rétention](#4-disk_snapshot_no_retention_policy---sans-politique-de-rétention)
  - [5. Snapshots d'Instances Supprimées](#5-disk_snapshot_deleted_vm---snapshots-dinstances-supprimées)
  - [6. Snapshots Failed](#6-disk_snapshot_failed---snapshots-failed)
  - [7. Snapshots Non Tagués](#7-disk_snapshot_untagged---snapshots-non-tagués)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Rétention Excessive Non-Prod](#8-disk_snapshot_excessive_retention_nonprod---rétention-excessive-non-prod)
  - [9. Snapshots Dupliqués](#9-disk_snapshot_duplicate---snapshots-dupliqués)
  - [10. Jamais Restaurés](#10-disk_snapshot_never_restored---jamais-restaurés)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte Disk Snapshots

**Disk Snapshots** sont des backups **incrémentaux** de Persistent Disks GCP, offrant :

- **Incremental backups** (seules modifications depuis dernier snapshot)
- **Read-only** (pour restore vers nouveau disk)
- **Cross-regional** (stockés dans Cloud Storage)
- **Point-in-time recovery** (restore disk à état spécifique)
- **Cost-effective** ($0.026/GB/mois vs $0.040+/GB/mois pour disks)

### Architecture Snapshots

```
Persistent Disk (1 TB)
│
├── Snapshot 1 (Day 0) ────────► FULL: 1 TB
│                                 Cost: $26/mois
│
├── Snapshot 2 (Day 7) ────────► DELTA: +100 GB (modifications)
│                                 Total: 1.1 TB
│                                 Cost: $28.60/mois
│
├── Snapshot 3 (Day 14) ───────► DELTA: +50 GB
│                                 Total: 1.15 TB
│                                 Cost: $29.90/mois
│
└── Snapshot 4 (Day 21) ───────► DELTA: +80 GB
                                  Total: 1.23 TB
                                  Cost: $31.98/mois

Si source disk DELETED:
└── Dernier snapshot devient "standalone" (non incrémental)
    Storage: 1.23 TB perpetual
    Cost: $31.98/mois ❌ WASTE si purpose unclear
```

### Caractéristiques Principales

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Incremental** | Seules modifications depuis dernier snapshot | Optimise storage |
| **Storage type** | Standard ($0.026/GB) vs Multi-regional ($0.032/GB) | +23% multi-regional |
| **Source disk** | Peut être deleted (snapshot devient orphan) | Risk perpetual waste |
| **Status** | CREATING, READY, FAILED, DELETING | FAILED still charges |
| **Labels** | Pour governance et cost allocation | Sans labels = confusion |
| **Lifecycle** | Resource policies (automated retention) | Sans policy = accumulation |

### Snapshot Pricing Tiers

| Storage Type | Prix/GB/Mois | Use Case | Availability |
|--------------|-------------|----------|--------------|
| **Standard** | $0.026 | Snapshots régionaux | Single region |
| **Multi-Regional** | $0.032 | DR, compliance | Multiple regions |
| **Archive** | $0.0012 | Long-term retention (not yet available for snapshots) | Future |

### Waste Typique

1. **Orphaned snapshots** : Source disk deleted = $100-1,000/mois perpetual waste
2. **Redundant snapshots** : >5 per disk = surcoût
3. **Never restored** : Created but never used = waste
4. **Excessive retention** : Dev/test 365+ days = surcoût
5. **Failed snapshots** : Status FAILED but storage consumed
6. **No lifecycle policy** : Manual snapshots s'accumulent sans limite
7. **Multi-regional unnecessary** : Dev/test doesn't need multi-region

---

## Modèle de Pricing Disk Snapshots

### Snapshot Storage Pricing

#### Standard Storage (Regional)

```
Prix: $0.026/GB/mois
Réplication: Single region (3 zones)
Use case: Backups régionaux, DR local
```

**Exemples :**
- 100 GB : 100 × $0.026 = **$2.60/mois**
- 1 TB : 1,000 × $0.026 = **$26.00/mois**
- 10 TB : 10,000 × $0.026 = **$260.00/mois**

#### Multi-Regional Storage

```
Prix: $0.032/GB/mois (+23% vs standard)
Réplication: Multiple regions
Use case: Global DR, compliance requirements
```

**Exemples :**
- 100 GB : 100 × $0.032 = **$3.20/mois**
- 1 TB : 1,000 × $0.032 = **$32.00/mois**
- 10 TB : 10,000 × $0.032 = **$320.00/mois**

### Comparaison avec Persistent Disks

| Resource | Prix/GB/Mois | Use Case | Read/Write |
|----------|-------------|----------|------------|
| **Snapshot (standard)** | $0.026 | Backup, restore | Read-only |
| **pd-standard (HDD)** | $0.040 | Active storage | Read/Write |
| **pd-balanced (SSD)** | $0.100 | General workloads | Read/Write |
| **pd-ssd (High-perf)** | $0.170 | Databases | Read/Write |

**Snapshot = 35% moins cher que pd-standard** (mais read-only)

---

### Incremental Snapshots Model

#### Scénario 1 : Snapshots Incrémentaux Normaux

```
Disk initial: 1 TB

Day 0 (Snapshot 1 - FULL):
─────────────────────────────
Storage: 1,000 GB
Cost: 1,000 × $0.026 = $26.00/mois

Day 7 (Snapshot 2 - DELTA):
─────────────────────────────
Modifications: 100 GB
Storage total: 1,100 GB
Cost: 1,100 × $0.026 = $28.60/mois (+$2.60)

Day 14 (Snapshot 3 - DELTA):
─────────────────────────────
Modifications: 50 GB
Storage total: 1,150 GB
Cost: 1,150 × $0.026 = $29.90/mois (+$1.30)

Day 21 (Snapshot 4 - DELTA):
─────────────────────────────
Modifications: 80 GB
Storage total: 1,230 GB
Cost: 1,230 × $0.026 = $31.98/mois (+$2.08)

Total: 4 snapshots, 1.23 TB storage
Cost: $31.98/mois
```

#### Scénario 2 : Source Disk Deleted (Orphan)

```
Disk deleted après Snapshot 4

Snapshot 4 becomes "standalone":
─────────────────────────────
Snapshot chain broken
Storage: 1,230 GB (full snapshot now)
Cost: 1,230 × $0.026 = $31.98/mois ❌
Duration: PERPETUAL (until manually deleted)

Waste: $31.98/mois × 12 = $383.76/an
```

#### Scénario 3 : Excessive Retention (365 daily snapshots)

```
Disk: 500 GB
Daily snapshots: 365

Snapshot 1 (full): 500 GB
Snapshots 2-365 (delta): avg 10 GB each = 3,640 GB
─────────────────────────────
Total: 4,140 GB
Cost: 4,140 × $0.026 = $107.64/mois

Recommandé: 30 snapshots (1 month retention)
Snapshot 1 (full): 500 GB
Snapshots 2-30 (delta): 290 GB
Total: 790 GB
Cost: 790 × $0.026 = $20.54/mois ✅

Waste: $107.64 - $20.54 = $87.10/mois ❌
Annual waste: $1,045.20/an
```

---

### Exemples Coûts Mensuels

#### Scénario 1 : Backup Normal (4 weekly snapshots)

```
Disk: 1 TB
4 weekly snapshots
─────────────────────────────
Snapshot 1 (full): 1,000 GB
Snapshots 2-4 (delta): 150 GB total
─────────────────────────────
Total: 1,150 GB × $0.026 = $29.90/mois
```

#### Scénario 2 : Orphaned Snapshots (10 disks deleted)

```
10 disks deleted (1 TB each)
10 orphan snapshot chains (avg 1.2 TB each)
─────────────────────────────
Total: 12,000 GB × $0.026 = $312/mois ❌ WASTE
Annual: $3,744/an
```

#### Scénario 3 : Redundant Snapshots (10 snapshots per disk)

```
Disk: 500 GB
10 snapshots (excessive)
─────────────────────────────
Snapshot 1 (full): 500 GB
Snapshots 2-10 (delta): 450 GB total
Total: 950 GB

Recommandé: 5 snapshots
Total: 600 GB

Waste: 350 GB × $0.026 = $9.10/mois
Per 10 disks: $91/mois, $1,092/an ❌
```

#### Scénario 4 : Multi-Regional Waste (Dev/Test)

```
Dev disks: 10 × 1 TB
4 snapshots each (multi-regional)
─────────────────────────────
Total: 40 TB

Multi-regional cost: 40,000 × $0.032 = $1,280/mois
Standard cost: 40,000 × $0.026 = $1,040/mois ✅

Waste: $240/mois, $2,880/an ❌
(Multi-regional unnecessary for dev/test)
```

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `disk_snapshot_orphaned` - Snapshots Orphelins

#### Détection

**Logique :**
```python
# 1. Lister tous les snapshots
from google.cloud import compute_v1

compute_client = compute_v1.SnapshotsClient()

request = compute_v1.ListSnapshotsRequest(
    project=project_id
)

snapshots = compute_client.list(request=request)

# 2. Pour chaque snapshot, vérifier si source disk existe
disks_client = compute_v1.DisksClient()

for snapshot in snapshots:
    source_disk = snapshot.source_disk  # Full URI ou None

    if source_disk:
        # Extraire zone et disk name du URI
        # Format: https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/disks/{disk}
        parts = source_disk.split('/')
        zone = parts[-3]
        disk_name = parts[-1]

        # 3. Vérifier si disk existe
        try:
            disk_request = compute_v1.GetDiskRequest(
                project=project_id,
                zone=zone,
                disk=disk_name
            )
            disk = disks_client.get(request=disk_request)
            # Disk exists = OK

        except Exception as e:
            # 4. Disk not found (404) = orphaned snapshot

            # Calculer age snapshot
            creation_timestamp = parse_timestamp(snapshot.creation_timestamp)
            age_days = (datetime.utcnow() - creation_timestamp).days

            # 5. Détection si orphan depuis longtemps
            if age_days >= orphan_age_threshold_days:
                # Snapshot orphelin = waste détecté

                # Calculer coût
                size_gb = snapshot.storage_bytes / (1024**3)
                monthly_cost = size_gb * 0.026  # Standard storage
```

**Critères :**
- `source_disk` reference → disk not found (404)
- `age >= 30 days` (orphan depuis 30+ jours)
- `status = 'READY'` (utilisable mais source gone)

**API Calls :**
```python
# Compute Engine API - Snapshots
compute_client = compute_v1.SnapshotsClient()
snapshots = compute_client.list(project=project_id)

# Compute Engine API - Disks (pour vérifier existence)
disks_client = compute_v1.DisksClient()
disk = disks_client.get(project=project_id, zone=zone, disk=disk_name)
```

#### Calcul de Coût

**Formule :**

Snapshot orphelin = 100% waste (source gone, purpose unclear) :

```python
# Récupérer taille snapshot
size_gb = snapshot.storage_bytes / (1024**3)

# Déterminer storage type (standard ou multi-regional)
storage_locations = snapshot.storage_locations  # List de regions
if len(storage_locations) > 1:
    # Multi-regional
    price_per_gb = 0.032
else:
    # Standard (regional)
    price_per_gb = 0.026

# Coût mensuel = 100% waste (orphan)
monthly_cost = size_gb * price_per_gb

# Coût gaspillé depuis source disk deleted
# Note: difficile de savoir exactement quand disk deleted
# Utiliser age snapshot comme proxy
age_days = (now - snapshot.creation_timestamp).days
age_months = age_days / 30.0

already_wasted = monthly_cost * age_months
```

**Exemple :**

Snapshot 1.2 TB orphelin depuis 90 jours :
```python
size_gb = 1200
price_per_gb = 0.026
monthly_cost = 1200 * 0.026 = $31.20
already_wasted = $31.20 * (90/30) = $93.60
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `orphan_age_threshold_days` | int | 30 | Âge min snapshot orphelin |
| `min_size_gb` | float | 1.0 | Taille min pour détection |
| `storage_type` | str | `'standard'` | Standard ou multi-regional |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-1234567890",
  "resource_name": "disk-backup-2024-05-15",
  "resource_type": "disk_snapshot_orphaned",
  "project_id": "my-project-123",
  "creation_time": "2024-05-15T10:00:00Z",
  "age_days": 171,
  "source_disk": "projects/my-project/zones/us-central1-a/disks/deleted-disk",
  "source_disk_exists": false,
  "storage_bytes": 1288490188800,
  "size_gb": 1200.0,
  "storage_locations": ["us-central1"],
  "storage_type": "standard",
  "status": "READY",
  "estimated_monthly_cost": 31.20,
  "already_wasted": 178.32,
  "confidence": "high",
  "recommendation": "Delete orphaned snapshot - source disk no longer exists",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `disk_snapshot_redundant` - Snapshots Redondants

#### Détection

**Logique :**
```python
# 1. Lister tous les snapshots
snapshots = compute_client.list(project=project_id)

# 2. Grouper snapshots par source_disk
from collections import defaultdict

snapshots_by_disk = defaultdict(list)

for snapshot in snapshots:
    source_disk = snapshot.source_disk

    if source_disk:
        snapshots_by_disk[source_disk].append(snapshot)

# 3. Pour chaque disk, vérifier count snapshots
for source_disk, snapshots_list in snapshots_by_disk.items():
    snapshot_count = len(snapshots_list)

    # 4. Détection si trop de snapshots
    if snapshot_count > max_snapshots_per_disk:
        # Trop de snapshots = redundant

        # Trier snapshots par date (plus récent en premier)
        snapshots_list.sort(key=lambda s: s.creation_timestamp, reverse=True)

        # Snapshots à conserver (ex: 5 derniers)
        snapshots_to_keep = snapshots_list[:recommended_snapshots_count]

        # Snapshots excess (à supprimer)
        snapshots_excess = snapshots_list[recommended_snapshots_count:]

        # Calculer waste
        excess_storage_gb = sum([s.storage_bytes / (1024**3) for s in snapshots_excess])
        monthly_waste = excess_storage_gb * 0.026
```

**Critères :**
- `snapshot_count > max_snapshots_per_disk` (défaut: 5)
- Source disk toujours existe (pas orphan)
- Recommandation : conserver 3-5 derniers snapshots

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)
```

#### Calcul de Coût

**Formule :**

Snapshots excess = waste :

```python
# Exemple: 10 snapshots pour 1 disk (recommandé: 5)

snapshots_list = [...]  # 10 snapshots triés par date

# Snapshots à conserver (5 derniers)
recommended_count = 5
snapshots_to_keep = snapshots_list[:recommended_count]

# Snapshots excess (5 anciens)
snapshots_excess = snapshots_list[recommended_count:]

# Calculer storage excess
excess_storage_gb = 0

for snapshot in snapshots_excess:
    size_gb = snapshot.storage_bytes / (1024**3)
    excess_storage_gb += size_gb

# Note: Snapshots incrémentaux, donc calcul complexe
# Approximation: utiliser taille totale des snapshots excess

# Coût excess
price_per_gb = 0.026
monthly_waste = excess_storage_gb * price_per_gb

# Si snapshots excess depuis plusieurs mois
avg_age_excess = sum([(now - s.creation_timestamp).days for s in snapshots_excess]) / len(snapshots_excess)
avg_months = avg_age_excess / 30.0
already_wasted = monthly_waste * avg_months
```

**Exemple :**

Disk avec 10 snapshots (recommandé: 5), excess storage 600 GB :
```python
excess_count = 5
excess_storage_gb = 600
monthly_waste = 600 * 0.026 = $15.60
already_wasted = $15.60 * 6 = $93.60 (si excess depuis 6 mois)
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `max_snapshots_per_disk` | int | 5 | Nombre max snapshots avant redundancy |
| `recommended_snapshots_count` | int | 3 | Nombre recommandé à conserver |
| `min_excess_storage_gb` | float | 10.0 | Storage excess min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "disk-with-redundant-snapshots",
  "resource_name": "prod-database-disk",
  "resource_type": "disk_snapshot_redundant",
  "project_id": "my-project-123",
  "source_disk": "projects/my-project/zones/us-central1-a/disks/prod-db-disk",
  "source_disk_exists": true,
  "snapshot_count": 10,
  "recommended_count": 5,
  "excess_count": 5,
  "snapshots_list": [
    {
      "snapshot_id": "snapshot-1",
      "creation_time": "2024-10-28T00:00:00Z",
      "size_gb": 120.5,
      "status": "READY"
    }
  ],
  "excess_storage_gb": 600.0,
  "estimated_monthly_waste": 15.60,
  "already_wasted": 93.60,
  "confidence": "high",
  "recommendation": "Delete 5 oldest snapshots - keep last 5 for recovery",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `disk_snapshot_old_unused` - Snapshots Vieux Jamais Restaurés

#### Détection

**Logique :**
```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Pour chaque snapshot, vérifier age
for snapshot in snapshots:
    creation_timestamp = parse_timestamp(snapshot.creation_timestamp)
    age_days = (datetime.utcnow() - creation_timestamp).days

    # 3. Détection si très vieux
    if age_days >= old_snapshot_threshold_days:
        # Snapshot >365 jours = potentially unused

        # 4. Vérifier si jamais restauré (via Cloud Logging)
        # Query Cloud Logging pour disk create from snapshot
        from google.cloud import logging_v2

        logging_client = logging_v2.Client()

        # Query logs: compute.disks.insert avec sourceSnapshot
        filter_str = f'''
        resource.type="gce_disk"
        AND protoPayload.methodName="v1.compute.disks.insert"
        AND protoPayload.request.sourceSnapshot="{snapshot.self_link}"
        '''

        # Lookback: depuis création snapshot
        entries = logging_client.list_entries(
            filter_=filter_str,
            max_results=1  # Just check if any restore exists
        )

        restore_count = len(list(entries))

        # 5. Si jamais restauré = unused
        if restore_count == 0:
            # Snapshot vieux jamais utilisé = waste

            size_gb = snapshot.storage_bytes / (1024**3)
            monthly_cost = size_gb * 0.026
```

**Critères :**
- `age >= 365 days` (1 an)
- `restore_count == 0` (jamais restauré dans logs)
- `status = 'READY'` (utilisable)

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)

# Cloud Logging API
from google.cloud import logging_v2
logging_client = logging_v2.Client()
entries = logging_client.list_entries(filter_=filter_str)
```

#### Calcul de Coût

**Formule :**

Snapshot vieux jamais restauré = waste :

```python
# Snapshot créé il y a 450 jours, jamais restauré

size_gb = snapshot.storage_bytes / (1024**3)
age_days = 450

# Coût mensuel
monthly_cost = size_gb * 0.026

# Coût gaspillé depuis création
# Note: snapshot peut avoir été utile initialement (backup safety)
# Waste = coût depuis 365 jours (retention excessive)
waste_days = age_days - 365  # 85 jours
waste_months = waste_days / 30.0

already_wasted = monthly_cost * waste_months
```

**Exemple :**

Snapshot 800 GB créé il y a 450 jours, jamais restauré :
```python
size_gb = 800
age_days = 450
monthly_cost = 800 * 0.026 = $20.80

waste_days = 450 - 365 = 85
waste_months = 85 / 30 = 2.83

already_wasted = $20.80 * 2.83 = $58.86
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `old_snapshot_threshold_days` | int | 365 | Âge min pour "old" |
| `check_restore_logs` | bool | true | Vérifier logs restore |
| `min_size_gb` | float | 10.0 | Taille min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-old-unused-789",
  "resource_name": "backup-2023-06-01",
  "resource_type": "disk_snapshot_old_unused",
  "project_id": "my-project-123",
  "creation_time": "2023-06-01T00:00:00Z",
  "age_days": 519,
  "source_disk": "projects/my-project/zones/us-central1-a/disks/old-app-disk",
  "size_gb": 800.0,
  "restore_count": 0,
  "last_restore_date": null,
  "estimated_monthly_cost": 20.80,
  "waste_months": 5.13,
  "already_wasted": 106.70,
  "confidence": "high",
  "recommendation": "Delete old snapshot - 519 days old, never restored",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `disk_snapshot_no_retention_policy` - Sans Politique de Rétention

#### Détection

**Logique :**
```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Lister resource policies (snapshot schedules)
policies_client = compute_v1.ResourcePoliciesClient()

resource_policies = {}

for region in regions:
    request = compute_v1.ListResourcePoliciesRequest(
        project=project_id,
        region=region
    )

    policies = policies_client.list(request=request)

    for policy in policies:
        if policy.snapshot_schedule_policy:
            resource_policies[policy.self_link] = policy

# 3. Pour chaque snapshot, vérifier si automated ou manual
for snapshot in snapshots:
    # Check if snapshot created by schedule (auto-delete enabled)
    # Automated snapshots have source_snapshot_schedule_policy

    if not snapshot.source_snapshot_schedule_policy:
        # Manual snapshot (no automated policy)

        # 4. Check labels pour user-managed retention
        labels = snapshot.labels if snapshot.labels else {}
        retention_days = labels.get('retention_days', None)

        if not retention_days:
            # No retention policy = risk accumulation

            # Calculer age
            age_days = (now - snapshot.creation_timestamp).days

            # 5. Détection si old manual snapshot sans policy
            if age_days >= manual_snapshot_threshold_days:
                # Manual snapshot sans retention = waste risk
```

**Critères :**
- `source_snapshot_schedule_policy IS NULL` (manual snapshot)
- `labels.retention_days IS NULL` (pas de retention user-defined)
- `age >= 90 days` (manual snapshot ancien)

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)

# Resource Policies API
policies_client = compute_v1.ResourcePoliciesClient()
policies = policies_client.list(project=project_id, region=region)
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (risque accumulation) :

```python
# Manual snapshots sans retention policy = risque
# Coût direct faible, mais indicateur de mauvaise gouvernance

# Coût = snapshot actuel + projection accumulation

size_gb = snapshot.storage_bytes / (1024**3)
monthly_cost = size_gb * 0.026

# Projection: si snapshot créé mensuellement sans cleanup
# Après 1 an: 12 snapshots × size = waste

projected_annual_snapshots = 12
projected_storage_gb = size_gb * projected_annual_snapshots
projected_annual_cost = projected_storage_gb * 0.026 * 12

# Waste actuel = governance overhead (5%)
governance_waste_pct = 0.05
monthly_waste = monthly_cost * governance_waste_pct
```

**Exemple :**

Manual snapshot 500 GB sans retention policy :
```python
size_gb = 500
monthly_cost = 500 * 0.026 = $13.00

# Governance waste
monthly_waste = $13.00 * 0.05 = $0.65/mois

# Projection accumulation (12 mois)
projected_storage = 500 * 12 = 6,000 GB
projected_cost = 6000 * 0.026 = $156/mois (après 1 an)
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `manual_snapshot_threshold_days` | int | 90 | Âge min manual snapshot |
| `check_retention_labels` | bool | true | Vérifier labels retention |
| `governance_waste_pct` | float | 0.05 | % coût gouvernance |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-manual-no-policy-456",
  "resource_name": "manual-backup-prod-db",
  "resource_type": "disk_snapshot_no_retention_policy",
  "project_id": "my-project-123",
  "creation_time": "2024-05-01T00:00:00Z",
  "age_days": 185,
  "source_snapshot_schedule_policy": null,
  "is_manual": true,
  "labels": {},
  "retention_policy": null,
  "size_gb": 500.0,
  "estimated_monthly_cost": 13.00,
  "governance_waste_monthly": 0.65,
  "projected_annual_accumulation_gb": 6000.0,
  "projected_annual_cost": 156.00,
  "confidence": "medium",
  "recommendation": "Add retention policy or label with retention_days to prevent accumulation",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `disk_snapshot_deleted_vm` - Snapshots d'Instances Supprimées

#### Détection

**Logique :**
```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Pour chaque snapshot, vérifier labels ou description
instances_client = compute_v1.InstancesClient()

for snapshot in snapshots:
    labels = snapshot.labels if snapshot.labels else {}
    description = snapshot.description if snapshot.description else ''

    # 3. Extraire instance name depuis labels ou description
    instance_name = labels.get('instance_name') or labels.get('vm_name')

    if not instance_name:
        # Essayer parser description
        # Format: "Snapshot of disk from instance {name}"
        import re
        match = re.search(r'instance\s+([a-z0-9-]+)', description, re.IGNORECASE)
        if match:
            instance_name = match.group(1)

    if instance_name:
        # 4. Vérifier si instance existe
        # Note: instance peut être dans n'importe quelle zone
        instance_exists = False

        for zone in zones:
            try:
                request = compute_v1.GetInstanceRequest(
                    project=project_id,
                    zone=zone,
                    instance=instance_name
                )
                instance = instances_client.get(request=request)
                instance_exists = True
                break
            except:
                continue

        # 5. Détection si instance deleted
        if not instance_exists:
            # Snapshot d'instance supprimée = purpose unclear

            age_days = (now - snapshot.creation_timestamp).days

            if age_days >= deleted_vm_threshold_days:
                # Snapshot d'instance supprimée = waste
```

**Critères :**
- `labels.instance_name` ou description contains instance name
- Instance not found in any zone
- `age >= 30 days` (VM deleted depuis 30+ jours)

**API Calls :**
```python
# Compute Engine API - Snapshots
snapshots = compute_client.list(project=project_id)

# Compute Engine API - Instances (vérifier existence)
instances_client = compute_v1.InstancesClient()
instance = instances_client.get(project=project_id, zone=zone, instance=instance_name)
```

#### Calcul de Coût

**Formule :**

Snapshot d'instance supprimée = waste (purpose unclear) :

```python
# VM deleted → snapshot purpose unclear

size_gb = snapshot.storage_bytes / (1024**3)
monthly_cost = size_gb * 0.026

# Coût gaspillé depuis VM deletion
# Note: difficile de savoir exactement quand VM deleted
# Utiliser deleted_vm_threshold_days comme proxy

age_days = (now - snapshot.creation_timestamp).days
age_months = age_days / 30.0

already_wasted = monthly_cost * age_months
```

**Exemple :**

Snapshot 300 GB d'instance "app-server-prod" supprimée il y a 60 jours :
```python
size_gb = 300
monthly_cost = 300 * 0.026 = $7.80
already_wasted = $7.80 * 2 = $15.60
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `deleted_vm_threshold_days` | int | 30 | Âge min depuis VM deletion |
| `check_vm_labels` | bool | true | Vérifier labels instance |
| `parse_description` | bool | true | Parser description pour instance name |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-deleted-vm-123",
  "resource_name": "snapshot-app-server-prod-2024-08-15",
  "resource_type": "disk_snapshot_deleted_vm",
  "project_id": "my-project-123",
  "creation_time": "2024-08-15T10:00:00Z",
  "age_days": 79,
  "labels": {
    "instance_name": "app-server-prod",
    "environment": "production"
  },
  "instance_name": "app-server-prod",
  "instance_exists": false,
  "size_gb": 300.0,
  "estimated_monthly_cost": 7.80,
  "already_wasted": 20.54,
  "confidence": "high",
  "recommendation": "Delete snapshot - source VM deleted (purpose unclear)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `disk_snapshot_failed` - Snapshots Failed

#### Détection

**Logique :**
```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Filtrer snapshots avec status = FAILED
for snapshot in snapshots:
    # 3. Détection si status failed
    if snapshot.status == 'FAILED':
        # Snapshot failed = unusable mais storage consumed

        # Calculer coût
        size_gb = snapshot.storage_bytes / (1024**3)
        monthly_cost = size_gb * 0.026

        # Age
        age_days = (now - snapshot.creation_timestamp).days

        # 4. Si failed depuis longtemps
        if age_days >= failed_snapshot_threshold_days:
            # Failed snapshot = 100% waste

            age_months = age_days / 30.0
            already_wasted = monthly_cost * age_months
```

**Critères :**
- `status = 'FAILED'`
- `age >= 7 days` (failed depuis 7+ jours)
- Storage consommé mais snapshot unusable

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)
snapshot.status  # 'READY', 'CREATING', 'FAILED', 'DELETING'
```

#### Calcul de Coût

**Formule :**

Failed snapshot = 100% waste (unusable) :

```python
# Failed snapshot still charges storage

size_gb = snapshot.storage_bytes / (1024**3)
monthly_cost = size_gb * 0.026

# Coût gaspillé depuis creation
age_days = (now - snapshot.creation_timestamp).days
age_months = age_days / 30.0

already_wasted = monthly_cost * age_months
```

**Exemple :**

Failed snapshot 150 GB depuis 45 jours :
```python
size_gb = 150
monthly_cost = 150 * 0.026 = $3.90
already_wasted = $3.90 * (45/30) = $5.85
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `failed_snapshot_threshold_days` | int | 7 | Âge min failed snapshot |
| `min_size_gb` | float | 1.0 | Taille min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-failed-789",
  "resource_name": "failed-backup-attempt",
  "resource_type": "disk_snapshot_failed",
  "project_id": "my-project-123",
  "creation_time": "2024-09-18T15:30:00Z",
  "age_days": 45,
  "status": "FAILED",
  "status_message": "Snapshot creation failed: source disk deleted during operation",
  "size_gb": 150.0,
  "estimated_monthly_cost": 3.90,
  "already_wasted": 5.85,
  "confidence": "high",
  "recommendation": "Delete failed snapshot - unusable and consuming storage",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `disk_snapshot_untagged` - Snapshots Non Tagués

#### Détection

**Logique :**
```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Définir labels requis
required_labels = ['environment', 'owner', 'purpose', 'retention']

# 3. Pour chaque snapshot, vérifier labels
for snapshot in snapshots:
    labels = snapshot.labels if snapshot.labels else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged snapshot = governance waste

        # Calculer coût
        size_gb = snapshot.storage_bytes / (1024**3)
        monthly_cost = size_gb * 0.026

        # Governance waste = 5%
        governance_waste = monthly_cost * 0.05
```

**Critères :**
- Labels manquants parmi la liste requise
- Snapshot actif (status = READY)
- Age >7 jours (éviter faux positifs nouveaux snapshots)

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)
snapshot.labels  # Dict ou None
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Snapshots non tagués = confusion cleanup decisions
# Coût estimé = 5% du coût snapshot

size_gb = snapshot.storage_bytes / (1024**3)
monthly_cost = size_gb * 0.026

# Governance waste = 5%
governance_waste_pct = 0.05
monthly_waste = monthly_cost * governance_waste_pct

# Waste cumulé depuis création
age_months = age_days / 30.0
already_wasted = monthly_waste * age_months
```

**Exemple :**

Snapshot 400 GB sans labels depuis 120 jours :
```python
size_gb = 400
monthly_cost = 400 * 0.026 = $10.40
governance_waste = $10.40 * 0.05 = $0.52/mois
already_wasted = $0.52 * 4 = $2.08
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'purpose']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût gouvernance |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-untagged-999",
  "resource_name": "disk-backup-20241015",
  "resource_type": "disk_snapshot_untagged",
  "project_id": "my-project-123",
  "creation_time": "2024-07-05T08:00:00Z",
  "age_days": 120,
  "labels": {},
  "missing_labels": ["environment", "owner", "purpose", "retention"],
  "size_gb": 400.0,
  "estimated_monthly_cost": 10.40,
  "governance_waste_monthly": 0.52,
  "already_wasted": 2.08,
  "confidence": "medium",
  "recommendation": "Add required labels for governance and cleanup decisions",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `disk_snapshot_excessive_retention_nonprod` - Rétention Excessive Non-Prod

#### Détection

**Logique :**

Analyser snapshots dev/test avec retention excessive :

```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Pour chaque snapshot, vérifier labels environment
for snapshot in snapshots:
    labels = snapshot.labels if snapshot.labels else {}
    environment = labels.get('environment', '').lower()

    # 3. Détection si environment non-prod
    if environment in nonprod_labels:
        # Dev/test snapshot

        age_days = (now - snapshot.creation_timestamp).days

        # 4. Vérifier age excessive pour non-prod
        if age_days > nonprod_retention_days:
            # Retention excessive pour dev/test
            # Dev/test should have max 30-90 days retention

            # Calculer waste
            size_gb = snapshot.storage_bytes / (1024**3)
            monthly_cost = size_gb * 0.026

            # Waste = coût depuis nonprod_retention_days
            excess_days = age_days - nonprod_retention_days
            excess_months = excess_days / 30.0

            monthly_waste = monthly_cost
            already_wasted = monthly_cost * excess_months

        # 5. Alternative: compter snapshots per disk
        # Si >10 snapshots pour dev disk → excessive
```

**Critères :**
- `labels.environment in ['dev', 'test', 'staging']`
- `age > 90 days` (dev/test shouldn't keep long-term)
- OU `snapshot_count > 10` per dev disk

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)
snapshot.labels.get('environment')
```

#### Calcul de Coût

**Formule :**

Dev/test retention excessive = waste :

```python
# Dev/test snapshot >90 jours = excessive

size_gb = snapshot.storage_bytes / (1024**3)
age_days = 120  # Exemple
nonprod_retention_days = 90

# Coût mensuel
monthly_cost = size_gb * 0.026

# Excess retention
excess_days = age_days - nonprod_retention_days  # 30 jours
excess_months = excess_days / 30.0  # 1 mois

# Waste = coût pendant excess period
monthly_waste = monthly_cost
already_wasted = monthly_cost * excess_months
```

**Exemple :**

Dev snapshot 600 GB, 150 jours old (recommandé: 90 jours max) :
```python
size_gb = 600
age_days = 150
nonprod_retention_days = 90

monthly_cost = 600 * 0.026 = $15.60
excess_days = 150 - 90 = 60
excess_months = 60 / 30 = 2

already_wasted = $15.60 * 2 = $31.20
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `nonprod_labels` | list | `['dev', 'test', 'staging']` | Labels environnements non-prod |
| `nonprod_retention_days` | int | 90 | Retention max dev/test |
| `nonprod_max_snapshots` | int | 10 | Nombre max snapshots dev/test |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-dev-excessive-111",
  "resource_name": "dev-db-backup-2024-06-15",
  "resource_type": "disk_snapshot_excessive_retention_nonprod",
  "project_id": "my-project-123",
  "creation_time": "2024-06-15T00:00:00Z",
  "age_days": 140,
  "labels": {
    "environment": "dev",
    "team": "backend"
  },
  "size_gb": 600.0,
  "recommended_retention_days": 90,
  "excess_days": 50,
  "estimated_monthly_cost": 15.60,
  "already_wasted": 26.00,
  "confidence": "high",
  "recommendation": "Delete dev snapshot - 140 days old (dev retention should be max 90 days)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `disk_snapshot_duplicate` - Snapshots Dupliqués

#### Détection

**Logique :**

Identifier snapshots dupliqués (même contenu, timestamps proches) :

```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Grouper par source_disk
snapshots_by_disk = defaultdict(list)

for snapshot in snapshots:
    source_disk = snapshot.source_disk
    if source_disk:
        snapshots_by_disk[source_disk].append(snapshot)

# 3. Pour chaque disk, détecter duplicates
for source_disk, snapshots_list in snapshots_by_disk.items():
    # Trier par timestamp
    snapshots_list.sort(key=lambda s: s.creation_timestamp)

    # 4. Comparer snapshots adjacents
    duplicates = []

    for i in range(len(snapshots_list) - 1):
        snap1 = snapshots_list[i]
        snap2 = snapshots_list[i + 1]

        # Calculer time diff
        time_diff = (snap2.creation_timestamp - snap1.creation_timestamp).total_seconds() / 3600  # heures

        # Calculer size diff
        size1_gb = snap1.storage_bytes / (1024**3)
        size2_gb = snap2.storage_bytes / (1024**3)
        size_diff_gb = abs(size2_gb - size1_gb)

        # 5. Détection si duplicate
        if time_diff <= duplicate_time_window_hours and size_diff_gb <= size_tolerance_gb:
            # Snapshots créés dans 1h avec même taille = duplicates
            duplicates.append((snap1, snap2))

    # 6. Pour chaque duplicate pair, recommander supprimer oldest
    for snap1, snap2 in duplicates:
        # Keep newer snapshot (snap2), delete older (snap1)
        waste_gb = snap1.storage_bytes / (1024**3)
        monthly_waste = waste_gb * 0.026
```

**Critères :**
- Même source_disk
- `time_diff <= 1 hour` (créés presque en même temps)
- `size_diff <= 1 GB` (même contenu approximativement)

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)
```

#### Calcul de Coût

**Formule :**

Duplicate snapshot = waste (garder le plus récent) :

```python
# Duplicate snapshot pair detected

snap1_size_gb = snap1.storage_bytes / (1024**3)
snap2_size_gb = snap2.storage_bytes / (1024**3)

# Delete oldest (snap1), keep newest (snap2)
waste_gb = snap1_size_gb
monthly_waste = waste_gb * 0.026

# Coût gaspillé depuis création snap1
age_days = (now - snap1.creation_timestamp).days
age_months = age_days / 30.0

already_wasted = monthly_waste * age_months
```

**Exemple :**

2 snapshots 500 GB créés à 30 minutes d'intervalle :
```python
snap1_size_gb = 500
snap2_size_gb = 505  # Diff: 5 GB (< tolerance)
time_diff = 0.5 hours  # < 1 hour

# Duplicate detected
monthly_waste = 500 * 0.026 = $13.00
already_wasted = $13.00 * 3 = $39.00 (si 3 mois old)
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `duplicate_time_window_hours` | float | 1.0 | Time window pour duplicate detection |
| `size_tolerance_gb` | float | 1.0 | Size diff tolerance |
| `min_size_gb` | float | 10.0 | Taille min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "duplicate-snapshot-pair-222",
  "resource_name": "duplicate_detection",
  "resource_type": "disk_snapshot_duplicate",
  "project_id": "my-project-123",
  "source_disk": "projects/my-project/zones/us-central1-a/disks/prod-disk",
  "duplicate_snapshots": [
    {
      "snapshot_id": "snapshot-1",
      "creation_time": "2024-10-15T10:00:00Z",
      "size_gb": 500.0,
      "status": "READY",
      "keep": false
    },
    {
      "snapshot_id": "snapshot-2",
      "creation_time": "2024-10-15T10:30:00Z",
      "size_gb": 505.0,
      "status": "READY",
      "keep": true
    }
  ],
  "time_diff_hours": 0.5,
  "size_diff_gb": 5.0,
  "waste_snapshot_size_gb": 500.0,
  "estimated_monthly_waste": 13.00,
  "already_wasted": 6.50,
  "confidence": "high",
  "recommendation": "Delete older duplicate snapshot (snapshot-1) - created 30 min apart with same content",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `disk_snapshot_never_restored` - Jamais Restaurés

#### Détection

**Logique :**

Identifier snapshots jamais utilisés pour restore :

```python
# 1. Lister snapshots
snapshots = compute_client.list(project=project_id)

# 2. Pour chaque snapshot, vérifier usage restore
from google.cloud import logging_v2

logging_client = logging_v2.Client()

for snapshot in snapshots:
    creation_timestamp = snapshot.creation_timestamp
    age_days = (datetime.utcnow() - creation_timestamp).days

    # 3. Détection si old snapshot
    if age_days >= never_restored_threshold_days:
        # Snapshot >180 jours

        # 4. Query Cloud Logging pour disk restore operations
        # Logs: compute.disks.insert avec sourceSnapshot

        filter_str = f'''
        resource.type="gce_disk"
        AND protoPayload.methodName="v1.compute.disks.insert"
        AND protoPayload.request.sourceSnapshot="{snapshot.self_link}"
        AND timestamp>="{creation_timestamp.isoformat()}"
        '''

        entries = logging_client.list_entries(
            filter_=filter_str,
            max_results=1
        )

        restore_count = len(list(entries))

        # 5. Si jamais restauré
        if restore_count == 0:
            # Snapshot créé mais jamais utilisé = waste

            size_gb = snapshot.storage_bytes / (1024**3)
            monthly_cost = size_gb * 0.026

            # Waste = coût depuis never_restored_threshold
            waste_days = age_days - never_restored_threshold_days
            waste_months = waste_days / 30.0

            already_wasted = monthly_cost * waste_months
```

**Critères :**
- `age >= 180 days` (6 mois)
- `restore_count == 0` (jamais restauré dans Cloud Logging)
- `status = 'READY'` (utilisable)

**API Calls :**
```python
# Compute Engine API
snapshots = compute_client.list(project=project_id)

# Cloud Logging API
from google.cloud import logging_v2
logging_client = logging_v2.Client()
entries = logging_client.list_entries(filter_=filter_str)
```

#### Calcul de Coût

**Formule :**

Snapshot jamais restauré = waste :

```python
# Snapshot créé il y a 250 jours, jamais restauré

size_gb = snapshot.storage_bytes / (1024**3)
age_days = 250
never_restored_threshold_days = 180

# Coût mensuel
monthly_cost = size_gb * 0.026

# Waste = coût depuis threshold (70 jours)
waste_days = age_days - never_restored_threshold_days  # 70
waste_months = waste_days / 30.0  # 2.33

already_wasted = monthly_cost * waste_months
```

**Exemple :**

Snapshot 700 GB créé il y a 250 jours, jamais restauré :
```python
size_gb = 700
age_days = 250
never_restored_threshold_days = 180

monthly_cost = 700 * 0.026 = $18.20
waste_days = 250 - 180 = 70
waste_months = 70 / 30 = 2.33

already_wasted = $18.20 * 2.33 = $42.41
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `never_restored_threshold_days` | int | 180 | Âge min pour "never restored" |
| `check_restore_logs` | bool | true | Vérifier Cloud Logging |
| `min_size_gb` | float | 10.0 | Taille min pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "snapshot-never-restored-333",
  "resource_name": "backup-archive-2024-03-15",
  "resource_type": "disk_snapshot_never_restored",
  "project_id": "my-project-123",
  "creation_time": "2024-03-15T00:00:00Z",
  "age_days": 232,
  "source_disk": "projects/my-project/zones/us-central1-a/disks/archive-disk",
  "size_gb": 700.0,
  "restore_count": 0,
  "last_restore_date": null,
  "estimated_monthly_cost": 18.20,
  "waste_months": 1.73,
  "already_wasted": 31.49,
  "confidence": "high",
  "recommendation": "Delete snapshot - 232 days old, never restored (unclear purpose)",
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
export ZONE="us-central1-a"
gcloud config set project $PROJECT_ID

# Activer APIs requises
gcloud services enable compute.googleapis.com
gcloud services enable logging.googleapis.com
```

#### 2. Service Account

```bash
# Ajouter permissions Compute Engine
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/compute.viewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.viewer"

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

---

### Tests Unitaires - Créer Ressources Test

#### Scénario 1: Orphaned Snapshot

```bash
# Créer disk
gcloud compute disks create test-disk-orphan \
  --size=10GB \
  --zone=$ZONE

# Créer snapshot
gcloud compute disks snapshot test-disk-orphan \
  --snapshot-names=test-orphan-snapshot \
  --zone=$ZONE

# DELETE disk (snapshot devient orphan)
gcloud compute disks delete test-disk-orphan \
  --zone=$ZONE \
  --quiet

# Vérifier snapshot existe, source deleted
gcloud compute snapshots list --filter="name:test-orphan-snapshot"
```

**Validation attendue :**
```json
{
  "resource_type": "disk_snapshot_orphaned",
  "source_disk_exists": false,
  "estimated_monthly_cost": "0.26"
}
```

---

#### Scénario 2: Redundant Snapshots

```bash
# Créer disk
gcloud compute disks create test-disk-redundant \
  --size=100GB \
  --zone=$ZONE

# Créer 10 snapshots (excessive)
for i in {1..10}; do
  gcloud compute disks snapshot test-disk-redundant \
    --snapshot-names=redundant-snap-$i \
    --zone=$ZONE
  sleep 60  # Wait 1 min between snapshots
done

# Vérifier count
gcloud compute snapshots list --filter="sourceDisk:test-disk-redundant" --format="table(name,creationTimestamp)"
```

**Validation attendue :**
```json
{
  "resource_type": "disk_snapshot_redundant",
  "snapshot_count": 10,
  "recommended_count": 5,
  "excess_count": 5
}
```

---

#### Scénario 6: Failed Snapshot

```bash
# Créer disk
gcloud compute disks create test-disk-fail \
  --size=10GB \
  --zone=$ZONE

# Lancer snapshot en background
gcloud compute disks snapshot test-disk-fail \
  --snapshot-names=failed-snapshot \
  --zone=$ZONE &

SNAPSHOT_PID=$!

# Immédiatement delete disk (va causer snapshot failure)
sleep 2
gcloud compute disks delete test-disk-fail \
  --zone=$ZONE \
  --quiet

# Wait for snapshot operation
wait $SNAPSHOT_PID

# Vérifier status
gcloud compute snapshots describe failed-snapshot --format="value(status)"
```

**Validation attendue :**
```json
{
  "resource_type": "disk_snapshot_failed",
  "status": "FAILED",
  "estimated_monthly_cost": ">= 0.26"
}
```

---

#### Scénario 7: Untagged Snapshot

```bash
# Créer disk
gcloud compute disks create test-disk-untagged \
  --size=50GB \
  --zone=$ZONE

# Créer snapshot SANS labels
gcloud compute disks snapshot test-disk-untagged \
  --snapshot-names=untagged-snapshot \
  --zone=$ZONE
  # NO --labels flag

# Vérifier labels vides
gcloud compute snapshots describe untagged-snapshot --format="value(labels)"
```

**Validation attendue :**
```json
{
  "resource_type": "disk_snapshot_untagged",
  "labels": {},
  "missing_labels": ["environment", "owner", "purpose"]
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script validation Disk Snapshots waste detection
"""

from google.cloud import compute_v1
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    snapshots_client = compute_v1.SnapshotsClient()
    disks_client = compute_v1.DisksClient()

    scenarios_detected = {
        'orphaned': 0,
        'redundant': 0,
        'old_unused': 0,
        'no_retention_policy': 0,
        'deleted_vm': 0,
        'failed': 0,
        'untagged': 0,
        'excessive_retention_nonprod': 0,
        'duplicate': 0,
        'never_restored': 0,
    }

    # List all snapshots
    request = compute_v1.ListSnapshotsRequest(project=PROJECT_ID)
    snapshots = list(snapshots_client.list(request=request))

    print(f"✅ Found {len(snapshots)} snapshots")

    # Test 1: Orphaned snapshots
    for snapshot in snapshots:
        source_disk = snapshot.source_disk
        if source_disk:
            # Extract zone and disk name
            parts = source_disk.split('/')
            if len(parts) >= 4:
                zone = parts[-3]
                disk_name = parts[-1]

                try:
                    disk_request = compute_v1.GetDiskRequest(
                        project=PROJECT_ID,
                        zone=zone,
                        disk=disk_name
                    )
                    disk = disks_client.get(request=disk_request)
                except:
                    # Disk not found = orphan
                    scenarios_detected['orphaned'] += 1
                    print(f"✅ Scenario 1 (orphaned): {snapshot.name}")

    # Test 6: Failed snapshots
    failed_snapshots = [s for s in snapshots if s.status == 'FAILED']
    scenarios_detected['failed'] = len(failed_snapshots)
    print(f"✅ Scenario 6 (failed): {len(failed_snapshots)} snapshots")

    # Test 7: Untagged snapshots
    untagged_snapshots = [s for s in snapshots if not s.labels or len(s.labels) == 0]
    scenarios_detected['untagged'] = len(untagged_snapshots)
    print(f"✅ Scenario 7 (untagged): {len(untagged_snapshots)} snapshots")

    # Rapport final
    print("\n📊 Detection Summary:")
    total_waste = sum(scenarios_detected.values())
    for scenario, count in scenarios_detected.items():
        if count > 0:
            print(f"  - {scenario}: {count} snapshots")

    print(f"\n✅ Total waste snapshots detected: {total_waste}")

if __name__ == '__main__':
    test_all_scenarios()
```

**Exécution :**
```bash
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
python3 validate_disk_snapshots_scenarios.py
```

---

### Cleanup

```bash
# Delete all test snapshots
gcloud compute snapshots delete test-orphan-snapshot --quiet
gcloud compute snapshots delete redundant-snap-{1..10} --quiet
gcloud compute snapshots delete failed-snapshot --quiet
gcloud compute snapshots delete untagged-snapshot --quiet

# Delete test disks
gcloud compute disks delete test-disk-redundant --zone=$ZONE --quiet
gcloud compute disks delete test-disk-untagged --zone=$ZONE --quiet
```

---

## Références

### Documentation GCP

- [Disk Snapshots API](https://cloud.google.com/compute/docs/reference/rest/v1/snapshots)
- [Snapshot Pricing](https://cloud.google.com/compute/disks-image-pricing#disk)
- [Snapshots Best Practices](https://cloud.google.com/compute/docs/disks/snapshot-best-practices)
- [Incremental Snapshots](https://cloud.google.com/compute/docs/disks/snapshots)
- [Snapshot Schedules](https://cloud.google.com/compute/docs/disks/scheduled-snapshots)
- [Resource Policies](https://cloud.google.com/compute/docs/disks/scheduled-snapshots#create_snapshot_schedule)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing 27 ressources GCP
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md) - Related resource
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md) - Related VMs

### Équivalences AWS/Azure

- **AWS EBS Snapshots** → GCP Disk Snapshots
- **Azure Disk Snapshots** → GCP Disk Snapshots
- **AWS Lifecycle Manager** → GCP Resource Policies (Snapshot Schedules)

### Best Practices

1. **Lifecycle Policies** : Use resource policies (snapshot schedules) for automated retention
2. **Labels** : Tag tous snapshots avec `environment`, `owner`, `purpose`, `retention`
3. **Retention** : Dev/test max 30-90 jours, production 180-365 jours
4. **Orphan Cleanup** : Delete orphaned snapshots (source disk deleted)
5. **Redundancy** : Max 3-5 snapshots per disk (unless compliance requirements)
6. **Failed Snapshots** : Delete immediately (unusable, still charges)
7. **Multi-Regional** : Use only for DR/compliance (23% more expensive)
8. **Restore Testing** : Test restores periodically (verify snapshots usable)
9. **Incremental** : Leverage incremental model (don't delete intermediate snapshots)
10. **Monitoring** : Track snapshot storage growth, set alerts

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
