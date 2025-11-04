# GCP Cloud Storage Buckets - Scénarios de Gaspillage (100%)

**Type de ressource :** `Storage : Cloud Storage Buckets`
**Catégorie :** Object Storage
**Impact financier estimé :** $10,000 - $50,000/an pour une organisation moyenne (500-2000 buckets)
**Complexité de détection :** ⭐⭐⭐⭐ (Élevée - Nécessite analyse logs d'accès + Storage Insights)

---

## Vue d'Ensemble

### Qu'est-ce que Cloud Storage ?

**Cloud Storage** est le service de stockage objet de GCP (équivalent AWS S3) pour stocker et accéder à des données non structurées :
- **Object storage** (fichiers, backups, archives, data lakes)
- **Globally accessible** (HTTP/HTTPS)
- **Highly durable** (99.999999999% durability - 11 nines)
- **Multiple storage classes** (Standard, Nearline, Coldline, Archive)
- **Lifecycle management** (transitions automatiques, suppression)

### Architecture Cloud Storage

```
Cloud Storage Bucket
│
├── Storage Classes (Pricing différent)
│   ├── Standard ($0.020/GB/mois)
│   │   ├── Use case: Données accédées fréquemment
│   │   ├── Retrieval cost: $0
│   │   └── Min storage duration: None
│   │
│   ├── Nearline ($0.010/GB/mois)
│   │   ├── Use case: Accès <1x/mois (backups 30 jours)
│   │   ├── Retrieval cost: $0.01/GB
│   │   └── Min storage duration: 30 jours
│   │
│   ├── Coldline ($0.004/GB/mois)
│   │   ├── Use case: Accès <1x/trimestre (90 jours)
│   │   ├── Retrieval cost: $0.02/GB
│   │   └── Min storage duration: 90 jours
│   │
│   └── Archive ($0.0012/GB/mois)
│       ├── Use case: Accès <1x/an (archives long-terme)
│       ├── Retrieval cost: $0.05/GB
│       └── Min storage duration: 365 jours
│
├── Features
│   ├── Versioning (keep old versions of objects)
│   ├── Lifecycle policies (auto-transition, deletion)
│   ├── Autoclass (automatic storage class management)
│   ├── Object metadata (custom-time, labels)
│   ├── Retention policies (WORM - Write Once Read Many)
│   └── Requester Pays (transfer costs to requester)
│
├── Location Types
│   ├── Multi-region (us, eu, asia) ──► $0.026/GB/mois (Standard)
│   ├── Dual-region (us-central1 + us-east1) ──► $0.024/GB/mois
│   └── Region (us-central1, europe-west1) ──► $0.020/GB/mois
│
└── Operations
    ├── Class A (write): $0.05/10K ops
    ├── Class B (read): $0.004/10K ops
    └── Network egress: $0.12/GB (general internet)
```

### Caractéristiques Principales

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Storage class** | Standard / Nearline / Coldline / Archive | 50-90% différence (Standard vs Archive) |
| **Versioning** | Keep old versions | 200-500% surcoût si pas de lifecycle |
| **Lifecycle** | Auto-transition + deletion | 60-80% économie si bien configuré |
| **Autoclass** | Auto storage class management | 30-50% économie (depuis Feb 2022) |
| **Location** | Multi-region / Dual-region / Region | 30% surcoût (multi vs region) |
| **Incomplete uploads** | Multipart uploads abandonnés | $100-1K/bucket waste |

### Cloud Storage Pricing (us-central1 - Region)

#### Storage Costs

| Storage Class | Prix/GB/mois | Retrieval/GB | Min Duration | Use Case |
|---------------|--------------|--------------|--------------|----------|
| **Standard** | $0.020 | $0 | None | Hot data, <30 days |
| **Nearline** | $0.010 | $0.01 | 30 days | Backups, <1x/mois |
| **Coldline** | $0.004 | $0.02 | 90 days | Disaster recovery, <1x/trimestre |
| **Archive** | $0.0012 | $0.05 | 365 days | Long-term archives, <1x/an |

**💡 Économie potentielle :**
```python
# 1 TB de données rarement accédées (1x/an)
data_tb = 1.0

# Standard
cost_standard = data_tb * 1024 * 0.020 * 12  # $245.76/an

# Archive
cost_archive = data_tb * 1024 * 0.0012 * 12 + (data_tb * 1024 * 0.05 * 1)  # $65.79/an

# Économie
savings = cost_standard - cost_archive  # $179.97/an (73% économie) ✅
```

#### Operations Costs

```python
# Class A Operations (write, list)
CLASS_A_PRICE = 0.05  # $/10K operations
# Examples: storage.objects.insert, storage.objects.list

# Class B Operations (read)
CLASS_B_PRICE = 0.004  # $/10K operations
# Examples: storage.objects.get

# Network Egress
EGRESS_PRICE = 0.12  # $/GB (general internet)
```

### Waste Typique

1. **Buckets vides** : Buckets sans objets = $10-50/bucket/an
2. **Wrong storage class** : Standard pour archives = 50-90% surcoût
3. **Versioning sans lifecycle** : Accumulation infinie versions = 200-500% surcoût
4. **Incomplete multipart uploads** : Uploads abandonnés = $100-1K/bucket
5. **Objects never accessed** : Objets jamais lus = $20-200/bucket/mois
6. **Lifecycle policy absente** : Pas d'optimisation auto = 60-80% surcoût
7. **Untagged buckets** : Sans labels = confusion cleanup

---

## Modèle de Pricing Cloud Storage

### Calcul Coût Total Bucket

```python
def calculate_bucket_monthly_cost(
    total_size_gb: float,
    storage_class: str,
    monthly_class_a_ops: int = 0,
    monthly_class_b_ops: int = 0,
    monthly_retrieval_gb: float = 0,
    monthly_egress_gb: float = 0,
    versioning_enabled: bool = False,
    noncurrent_versions_size_gb: float = 0
) -> float:
    """
    Calcule le coût mensuel total d'un bucket Cloud Storage.

    Args:
        total_size_gb: Taille totale des objets (GB)
        storage_class: 'STANDARD', 'NEARLINE', 'COLDLINE', 'ARCHIVE'
        monthly_class_a_ops: Nombre d'opérations Class A (write, list)
        monthly_class_b_ops: Nombre d'opérations Class B (read)
        monthly_retrieval_gb: GB retrieved (Nearline/Coldline/Archive)
        monthly_egress_gb: GB sortant vers internet
        versioning_enabled: Si versioning activé
        noncurrent_versions_size_gb: Taille versions non-courantes

    Returns:
        Coût mensuel total ($)
    """
    # 1. Storage costs
    storage_prices = {
        'STANDARD': 0.020,
        'NEARLINE': 0.010,
        'COLDLINE': 0.004,
        'ARCHIVE': 0.0012
    }

    storage_cost = total_size_gb * storage_prices[storage_class]

    # Versioning costs (noncurrent versions facturées pareil)
    if versioning_enabled:
        storage_cost += noncurrent_versions_size_gb * storage_prices[storage_class]

    # 2. Operations costs
    class_a_cost = (monthly_class_a_ops / 10_000) * 0.05
    class_b_cost = (monthly_class_b_ops / 10_000) * 0.004

    # 3. Retrieval costs (Nearline/Coldline/Archive only)
    retrieval_prices = {
        'STANDARD': 0,
        'NEARLINE': 0.01,
        'COLDLINE': 0.02,
        'ARCHIVE': 0.05
    }

    retrieval_cost = monthly_retrieval_gb * retrieval_prices[storage_class]

    # 4. Network egress costs
    egress_cost = monthly_egress_gb * 0.12

    # Total
    total_cost = storage_cost + class_a_cost + class_b_cost + retrieval_cost + egress_cost

    return total_cost
```

**Exemples de calcul :**

```python
# Exemple 1: Bucket Standard avec traffic élevé
cost_hot_data = calculate_bucket_monthly_cost(
    total_size_gb=500,
    storage_class='STANDARD',
    monthly_class_a_ops=100_000,
    monthly_class_b_ops=1_000_000,
    monthly_egress_gb=50
)
# = (500 * 0.020) + (100K/10K * 0.05) + (1M/10K * 0.004) + (50 * 0.12)
# = $10 + $0.50 + $0.40 + $6.00
# = $16.90/mois

# Exemple 2: Archive storage (rarement accédé)
cost_archive = calculate_bucket_monthly_cost(
    total_size_gb=2000,
    storage_class='ARCHIVE',
    monthly_class_a_ops=100,
    monthly_class_b_ops=500,
    monthly_retrieval_gb=10,  # 1x retrieve/mois
    monthly_egress_gb=10
)
# = (2000 * 0.0012) + (100/10K * 0.05) + (500/10K * 0.004) + (10 * 0.05) + (10 * 0.12)
# = $2.40 + $0.0005 + $0.0002 + $0.50 + $1.20
# = $4.10/mois vs $40/mois en Standard (90% économie)

# Exemple 3: Versioning sans lifecycle (problème)
cost_versioning_waste = calculate_bucket_monthly_cost(
    total_size_gb=100,
    storage_class='STANDARD',
    versioning_enabled=True,
    noncurrent_versions_size_gb=300  # 3x plus de versions que current
)
# = (100 * 0.020) + (300 * 0.020)
# = $2 + $6 = $8/mois
# Optimal (avec lifecycle): $2/mois (75% waste)
```

---

## Phase 1 : Détection Simple (7 Scénarios)

### Scénario 1 : Buckets Vides (Empty Buckets)

**Description :** Buckets créés mais sans aucun objet. Génèrent des coûts opérationnels + confusion.

**Impact financier :**
- **Coût mensuel :** $10-50/bucket/an (operations, metadata, monitoring)
- **Waste typique :** 10-20% des buckets sont vides
- **Économie annuelle :** $1K - $5K

**Logique de détection :**

```python
from google.cloud import storage
from datetime import datetime, timedelta

def detect_cloud_storage_empty_buckets(
    project_id: str,
    age_threshold_days: int = 30
) -> list:
    """
    Détecte les buckets Cloud Storage vides (0 objets).

    Args:
        project_id: ID du projet GCP
        age_threshold_days: Âge minimum pour considérer waste (défaut: 30 jours)

    Returns:
        Liste des buckets vides avec métadonnées
    """
    storage_client = storage.Client(project=project_id)

    empty_buckets = []

    # Lister tous les buckets
    for bucket in storage_client.list_buckets():
        # Compter objets (optimization: max_results=1 pour vérifier si vide)
        blobs = list(bucket.list_blobs(max_results=1))

        if len(blobs) == 0:
            # Bucket vide détecté

            # Calculer âge du bucket
            bucket_created = bucket.time_created
            age_days = (datetime.utcnow().replace(tzinfo=None) - bucket_created.replace(tzinfo=None)).days

            # Filtrer par âge
            if age_days >= age_threshold_days:
                # Niveau confiance
                if age_days >= 180:
                    confidence = "CRITICAL"
                elif age_days >= 90:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                empty_buckets.append({
                    "bucket_name": bucket.name,
                    "location": bucket.location,
                    "location_type": bucket.location_type,
                    "storage_class": bucket.storage_class,
                    "created_at": bucket_created.isoformat(),
                    "age_days": age_days,
                    "versioning_enabled": bucket.versioning_enabled,
                    "lifecycle_rules": len(bucket.lifecycle_rules) if bucket.lifecycle_rules else 0,
                    "labels": dict(bucket.labels) if bucket.labels else {},
                    "confidence": confidence,
                    "recommendation": f"Delete empty bucket (age: {age_days} days)",
                    "estimated_annual_waste": 25.00  # Approximation
                })

    return empty_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    empty = detect_cloud_storage_empty_buckets(
        project_id="my-gcp-project",
        age_threshold_days=30
    )

    print(f"✅ {len(empty)} buckets vides détectés")

    total_waste = sum([b["estimated_annual_waste"] for b in empty])
    print(f"💰 Waste estimé: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Bucket vide n'a pas de storage cost mais génère:
# - Metadata storage (~$1/an)
# - Monitoring costs (~$10-20/an)
# - Operations costs si LIST operations (~$5-10/an)

estimated_annual_cost_empty_bucket = 25.00  # $25/an
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `age_threshold_days` | 30 jours | Âge minimum bucket vide | ↑ = moins de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "empty_bucket",
  "bucket_name": "legacy-backup-bucket-2023",
  "location": "us-central1",
  "location_type": "region",
  "storage_class": "STANDARD",
  "created_at": "2023-03-15T10:00:00Z",
  "age_days": 290,
  "versioning_enabled": false,
  "lifecycle_rules": 0,
  "labels": {},
  "confidence": "CRITICAL",
  "recommendation": "Delete empty bucket (age: 290 days)",
  "estimated_annual_waste": 25.00
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_empty_buckets()`

---

### Scénario 2 : Objects dans Mauvaise Storage Class

**Description :** Objects stockés en Standard mais rarement accédés (devraient être en Nearline/Coldline/Archive).

**Impact financier :**
- **Surcoût mensuel :** 50-90% (Standard vs Archive)
- **Waste typique :** 30-50% des objects mal classifiés
- **Économie annuelle :** $5K - $25K

**Logique de détection :**

```python
from google.cloud import logging_v2
from collections import defaultdict

def detect_cloud_storage_wrong_storage_class(
    project_id: str,
    bucket_name: str,
    lookback_days: int = 90,
    no_access_nearline_days: int = 30,
    no_access_coldline_days: int = 90,
    no_access_archive_days: int = 365
) -> list:
    """
    Détecte objects en Standard storage non accédés depuis X jours.

    Recommandations :
    - 0 accès depuis 30 jours → Nearline (50% économie)
    - 0 accès depuis 90 jours → Coldline (80% économie)
    - 0 accès depuis 365 jours → Archive (94% économie)

    Args:
        project_id: ID du projet GCP
        bucket_name: Nom du bucket à analyser
        lookback_days: Période d'analyse (défaut: 90 jours)
        no_access_nearline_days: Seuil Nearline
        no_access_coldline_days: Seuil Coldline
        no_access_archive_days: Seuil Archive

    Returns:
        Liste des objects avec storage class suboptimal
    """
    storage_client = storage.Client(project=project_id)
    logging_client = logging_v2.Client(project=project_id)

    bucket = storage_client.bucket(bucket_name)

    # 1. Récupérer tous les objets en STANDARD
    standard_objects = []
    for blob in bucket.list_blobs():
        if blob.storage_class == 'STANDARD':
            standard_objects.append({
                "name": blob.name,
                "size_bytes": blob.size,
                "time_created": blob.time_created,
                "updated": blob.updated,
                "storage_class": blob.storage_class
            })

    if not standard_objects:
        return []

    # 2. Query Cloud Logging pour Data Access logs (storage.objects.get)
    # Note: Nécessite Data Access logging activé sur le bucket

    filter_str = f'''
    resource.type="gcs_bucket"
    resource.labels.bucket_name="{bucket_name}"
    protoPayload.methodName="storage.objects.get"
    timestamp>="{(datetime.utcnow() - timedelta(days=lookback_days)).isoformat()}Z"
    '''

    # Compter les accès par objet
    object_access_counts = defaultdict(int)

    try:
        for entry in logging_client.list_entries(filter_=filter_str, page_size=1000):
            # Extraire object name du log
            if hasattr(entry.payload, 'resource_name'):
                object_name = entry.payload.resource_name.split('/')[-1]
                object_access_counts[object_name] += 1
    except Exception as e:
        print(f"Warning: Could not query logs (Data Access logs may not be enabled): {e}")
        # Fallback: utiliser metadata.updated comme proxy
        pass

    # 3. Identifier objects avec 0 ou faibles accès
    wrong_storage_class_objects = []

    for obj in standard_objects:
        object_name = obj["name"]
        size_gb = obj["size_bytes"] / (1024 ** 3)

        # Nombre d'accès dans lookback period
        access_count = object_access_counts.get(object_name, 0)

        # Calculer jours depuis dernière modification (proxy si pas de logs)
        days_since_update = (datetime.utcnow().replace(tzinfo=None) - obj["updated"].replace(tzinfo=None)).days

        # Déterminer storage class recommandé
        recommended_class = None
        monthly_savings = 0

        if access_count == 0 or days_since_update >= no_access_archive_days:
            # Archive recommandé
            recommended_class = "ARCHIVE"
            current_cost = size_gb * 0.020 * 12  # Standard annual
            optimal_cost = size_gb * 0.0012 * 12  # Archive annual
            annual_savings = current_cost - optimal_cost
            monthly_savings = annual_savings / 12
            confidence = "HIGH" if days_since_update >= no_access_archive_days else "MEDIUM"

        elif access_count <= 1 or days_since_update >= no_access_coldline_days:
            # Coldline recommandé
            recommended_class = "COLDLINE"
            current_cost = size_gb * 0.020 * 12
            optimal_cost = size_gb * 0.004 * 12
            annual_savings = current_cost - optimal_cost
            monthly_savings = annual_savings / 12
            confidence = "HIGH" if days_since_update >= no_access_coldline_days else "MEDIUM"

        elif access_count <= 3 or days_since_update >= no_access_nearline_days:
            # Nearline recommandé
            recommended_class = "NEARLINE"
            current_cost = size_gb * 0.020 * 12
            optimal_cost = size_gb * 0.010 * 12
            annual_savings = current_cost - optimal_cost
            monthly_savings = annual_savings / 12
            confidence = "MEDIUM"

        if recommended_class:
            wrong_storage_class_objects.append({
                "bucket_name": bucket_name,
                "object_name": object_name,
                "size_gb": round(size_gb, 4),
                "size_bytes": obj["size_bytes"],
                "current_storage_class": "STANDARD",
                "recommended_storage_class": recommended_class,
                "access_count_lookback": access_count,
                "days_since_update": days_since_update,
                "monthly_cost_current": round(size_gb * 0.020, 4),
                "monthly_cost_optimal": round(size_gb * {'NEARLINE': 0.010, 'COLDLINE': 0.004, 'ARCHIVE': 0.0012}[recommended_class], 4),
                "monthly_savings": round(monthly_savings, 4),
                "annual_savings": round(monthly_savings * 12, 4),
                "confidence": confidence,
                "recommendation": f"Transition to {recommended_class} storage class",
            })

    return wrong_storage_class_objects


# Exemple d'utilisation
if __name__ == "__main__":
    wrong_class = detect_cloud_storage_wrong_storage_class(
        project_id="my-gcp-project",
        bucket_name="my-data-bucket",
        lookback_days=90
    )

    print(f"✅ {len(wrong_class)} objects avec storage class suboptimal")

    total_savings = sum([o["annual_savings"] for o in wrong_class])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Calcul du coût :**

```python
# Object 100 GB en Standard jamais accédé
size_gb = 100

# Coût actuel (Standard)
current_cost_monthly = size_gb * 0.020  # $2.00/mois

# Coût optimal (Archive)
optimal_cost_monthly = size_gb * 0.0012  # $0.12/mois

# Économie
monthly_savings = current_cost_monthly - optimal_cost_monthly  # $1.88/mois
annual_savings = monthly_savings * 12  # $22.56/an (94% économie)
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `lookback_days` | 90 jours | Période analyse accès | ↑ = plus conservateur |
| `no_access_nearline_days` | 30 jours | Seuil Nearline | ↓ = plus agressif |
| `no_access_coldline_days` | 90 jours | Seuil Coldline | ↓ = plus agressif |
| `no_access_archive_days` | 365 jours | Seuil Archive | ↓ = plus agressif |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_object",
  "waste_scenario": "wrong_storage_class",
  "bucket_name": "backup-data-2023",
  "object_name": "logs/application-2023-01.tar.gz",
  "size_gb": 45.3,
  "size_bytes": 48636313600,
  "current_storage_class": "STANDARD",
  "recommended_storage_class": "ARCHIVE",
  "access_count_lookback": 0,
  "days_since_update": 420,
  "monthly_cost_current": 0.906,
  "monthly_cost_optimal": 0.054,
  "monthly_savings": 0.852,
  "annual_savings": 10.224,
  "confidence": "HIGH",
  "recommendation": "Transition to ARCHIVE storage class"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_wrong_storage_class()`

---

### Scénario 3 : Versioning Sans Lifecycle Policy

**Description :** Versioning activé mais aucune lifecycle policy pour supprimer vieilles versions = accumulation infinie.

**Impact financier :**
- **Surcoût mensuel :** 200-500% (versions accumulent exponentiellement)
- **Waste typique :** 40-60% des buckets avec versioning
- **Économie annuelle :** $10K - $40K

**Logique de détection :**

```python
def detect_cloud_storage_versioning_without_lifecycle(
    project_id: str,
    min_noncurrent_versions: int = 10
) -> list:
    """
    Détecte buckets avec versioning mais sans lifecycle policy pour cleanup.

    Args:
        project_id: ID du projet GCP
        min_noncurrent_versions: Seuil minimum versions non-courantes

    Returns:
        Liste des buckets avec versioning waste
    """
    storage_client = storage.Client(project=project_id)

    versioning_waste_buckets = []

    for bucket in storage_client.list_buckets():
        # Vérifier si versioning activé
        if not bucket.versioning_enabled:
            continue

        # Vérifier lifecycle rules
        lifecycle_rules = bucket.lifecycle_rules if bucket.lifecycle_rules else []

        # Chercher rule qui supprime noncurrent versions
        has_noncurrent_deletion = False
        for rule in lifecycle_rules:
            action = rule.get('action', {})
            condition = rule.get('condition', {})

            if action.get('type') == 'Delete' and (
                'noncurrentTimeBefore' in condition or
                'numNewerVersions' in condition or
                'daysSinceNoncurrentTime' in condition
            ):
                has_noncurrent_deletion = True
                break

        # Si pas de cleanup policy, analyser le waste
        if not has_noncurrent_deletion:
            # Compter versions (current vs noncurrent)
            total_versions = 0
            current_versions = 0
            total_size_bytes = 0
            noncurrent_size_bytes = 0

            oldest_noncurrent = None

            for blob in bucket.list_blobs(versions=True):
                total_versions += 1
                total_size_bytes += blob.size

                # blob.generation == metageneration means current version
                if not blob.time_deleted:  # Current version
                    current_versions += 1
                else:  # Noncurrent version
                    noncurrent_size_bytes += blob.size
                    if not oldest_noncurrent or blob.time_deleted < oldest_noncurrent:
                        oldest_noncurrent = blob.time_deleted

            noncurrent_versions = total_versions - current_versions

            # Détection si nombre significatif de noncurrent versions
            if noncurrent_versions >= min_noncurrent_versions:
                # Calculer waste
                noncurrent_size_gb = noncurrent_size_bytes / (1024 ** 3)

                # Coût des noncurrent versions (même prix que current)
                storage_class = bucket.storage_class or 'STANDARD'
                storage_prices = {
                    'STANDARD': 0.020,
                    'NEARLINE': 0.010,
                    'COLDLINE': 0.004,
                    'ARCHIVE': 0.0012
                }

                monthly_waste = noncurrent_size_gb * storage_prices.get(storage_class, 0.020)
                annual_waste = monthly_waste * 12

                # Ratio waste
                waste_ratio = (noncurrent_size_bytes / total_size_bytes * 100) if total_size_bytes > 0 else 0

                # Âge oldest noncurrent version
                if oldest_noncurrent:
                    days_oldest = (datetime.utcnow().replace(tzinfo=None) - oldest_noncurrent.replace(tzinfo=None)).days
                else:
                    days_oldest = 0

                # Niveau confiance
                if noncurrent_versions > 100 or waste_ratio > 70:
                    confidence = "CRITICAL"
                elif noncurrent_versions > 50 or waste_ratio > 50:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"

                versioning_waste_buckets.append({
                    "bucket_name": bucket.name,
                    "location": bucket.location,
                    "storage_class": storage_class,
                    "versioning_enabled": True,
                    "lifecycle_rules_count": len(lifecycle_rules),
                    "has_noncurrent_deletion_policy": False,
                    "total_versions": total_versions,
                    "current_versions": current_versions,
                    "noncurrent_versions": noncurrent_versions,
                    "total_size_gb": round(total_size_bytes / (1024 ** 3), 4),
                    "noncurrent_size_gb": round(noncurrent_size_gb, 4),
                    "waste_ratio_pct": round(waste_ratio, 2),
                    "oldest_noncurrent_days": days_oldest,
                    "monthly_waste": round(monthly_waste, 2),
                    "annual_waste": round(annual_waste, 2),
                    "confidence": confidence,
                    "recommendation": f"Add lifecycle policy to delete noncurrent versions after 30 days",
                })

    return versioning_waste_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    versioning_waste = detect_cloud_storage_versioning_without_lifecycle(
        project_id="my-gcp-project",
        min_noncurrent_versions=10
    )

    print(f"✅ {len(versioning_waste)} buckets avec versioning waste")

    total_waste = sum([b["annual_waste"] for b in versioning_waste])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Bucket avec 100 GB current + 300 GB noncurrent versions
current_size_gb = 100
noncurrent_size_gb = 300

# Coût actuel (tout facturé)
monthly_cost_current = (current_size_gb + noncurrent_size_gb) * 0.020  # $8.00/mois

# Coût optimal (avec lifecycle: keep 3 dernières versions)
# Assume 3 versions = 20 GB noncurrent
optimal_noncurrent_gb = 20
monthly_cost_optimal = (current_size_gb + optimal_noncurrent_gb) * 0.020  # $2.40/mois

# Waste
monthly_waste = monthly_cost_current - monthly_cost_optimal  # $5.60/mois
annual_waste = monthly_waste * 12  # $67.20/an (70% waste)
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_noncurrent_versions` | 10 | Seuil versions non-courantes | ↓ = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "versioning_without_lifecycle",
  "bucket_name": "production-data-bucket",
  "location": "us-central1",
  "storage_class": "STANDARD",
  "versioning_enabled": true,
  "lifecycle_rules_count": 0,
  "has_noncurrent_deletion_policy": false,
  "total_versions": 4523,
  "current_versions": 1250,
  "noncurrent_versions": 3273,
  "total_size_gb": 850.5,
  "noncurrent_size_gb": 620.3,
  "waste_ratio_pct": 72.9,
  "oldest_noncurrent_days": 580,
  "monthly_waste": 12.41,
  "annual_waste": 148.86,
  "confidence": "CRITICAL",
  "recommendation": "Add lifecycle policy to delete noncurrent versions after 30 days"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_versioning_without_lifecycle()`

---

### Scénario 4 : Incomplete Multipart Uploads

**Description :** Uploads multipart abandonnés qui restent stockés et facturés indéfiniment.

**Impact financier :**
- **Coût mensuel :** $100 - $1K/bucket
- **Waste typique :** 15-30% des buckets ont uploads incomplets
- **Économie annuelle :** $2K - $10K

**Logique de détection :**

```python
from google.cloud import storage
from google.resumable_media import requests as resumable_requests
import requests

def detect_cloud_storage_incomplete_multipart_uploads(
    project_id: str,
    age_threshold_days: int = 7
) -> list:
    """
    Détecte incomplete multipart uploads (uploads résumables abandonnés).

    Note: GCP Cloud Storage utilise "resumable uploads" plutôt que multipart.
    Les uploads résumables abandonnés restent en storage pendant 7 jours par défaut,
    mais peuvent rester plus longtemps si le lifecycle n'est pas configuré.

    Args:
        project_id: ID du projet GCP
        age_threshold_days: Âge minimum uploads incomplets (défaut: 7 jours)

    Returns:
        Liste des buckets avec incomplete uploads
    """
    storage_client = storage.Client(project=project_id)

    incomplete_uploads_buckets = []

    for bucket in storage_client.list_buckets():
        # Check lifecycle policy for AbortIncompleteMultipartUpload
        lifecycle_rules = bucket.lifecycle_rules if bucket.lifecycle_rules else []

        has_abort_incomplete_policy = False
        for rule in lifecycle_rules:
            action = rule.get('action', {})
            condition = rule.get('condition', {})

            # GCS utilise "age" condition pour cleanup incomplete uploads
            if action.get('type') == 'Delete' and 'age' in condition:
                # Si age < 7 jours, considérer comme cleanup policy
                if condition['age'] <= 7:
                    has_abort_incomplete_policy = True
                    break

        # Si pas de policy, potentiel waste d'incomplete uploads
        if not has_abort_incomplete_policy:
            # Note: GCS n'expose pas directement la liste des uploads incomplets
            # via l'API standard. On détecte la configuration manquante.

            # Estimer taille potential waste basé sur bucket size
            total_size_gb = 0
            object_count = 0

            for blob in bucket.list_blobs(max_results=1000):
                total_size_gb += blob.size / (1024 ** 3)
                object_count += 1

            if object_count > 0:
                # Approximation: 1-5% du bucket peut être incomplete uploads
                estimated_incomplete_size_gb = total_size_gb * 0.02  # 2% estimate

                storage_class = bucket.storage_class or 'STANDARD'
                storage_prices = {
                    'STANDARD': 0.020,
                    'NEARLINE': 0.010,
                    'COLDLINE': 0.004,
                    'ARCHIVE': 0.0012
                }

                monthly_waste = estimated_incomplete_size_gb * storage_prices.get(storage_class, 0.020)
                annual_waste = monthly_waste * 12

                # Niveau confiance (LOW car estimation)
                if total_size_gb > 1000:
                    confidence = "MEDIUM"
                else:
                    confidence = "LOW"

                incomplete_uploads_buckets.append({
                    "bucket_name": bucket.name,
                    "location": bucket.location,
                    "storage_class": storage_class,
                    "has_abort_incomplete_policy": False,
                    "lifecycle_rules_count": len(lifecycle_rules),
                    "total_size_gb": round(total_size_gb, 2),
                    "estimated_incomplete_size_gb": round(estimated_incomplete_size_gb, 2),
                    "monthly_waste_estimated": round(monthly_waste, 2),
                    "annual_waste_estimated": round(annual_waste, 2),
                    "confidence": confidence,
                    "recommendation": "Add lifecycle policy to abort incomplete uploads after 7 days",
                    "lifecycle_rule_example": {
                        "action": {"type": "Delete"},
                        "condition": {"age": 7}
                    }
                })

    return incomplete_uploads_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    incomplete = detect_cloud_storage_incomplete_multipart_uploads(
        project_id="my-gcp-project"
    )

    print(f"⚠️  {len(incomplete)} buckets sans policy abort incomplete uploads")

    total_waste = sum([b["annual_waste_estimated"] for b in incomplete])
    print(f"💰 Waste estimé: ${total_waste:.2f}/an")
```

**Lifecycle policy recommandée :**

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 7
        }
      }
    ]
  }
}
```

**Calcul du coût :**

```python
# Bucket 500 GB avec 2% incomplete uploads
total_size_gb = 500
incomplete_pct = 0.02
incomplete_size_gb = total_size_gb * incomplete_pct  # 10 GB

# Coût waste (Standard)
monthly_waste = incomplete_size_gb * 0.020  # $0.20/mois
annual_waste = monthly_waste * 12  # $2.40/an

# Pour large buckets (10 TB)
large_bucket_gb = 10000
incomplete_large = large_bucket_gb * 0.02  # 200 GB
monthly_waste_large = incomplete_large * 0.020  # $4.00/mois
annual_waste_large = monthly_waste_large * 12  # $48/an
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `age_threshold_days` | 7 jours | Âge abort incomplete uploads | ↑ = plus de waste |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "incomplete_multipart_uploads",
  "bucket_name": "upload-staging-bucket",
  "location": "us-central1",
  "storage_class": "STANDARD",
  "has_abort_incomplete_policy": false,
  "lifecycle_rules_count": 0,
  "total_size_gb": 1250.5,
  "estimated_incomplete_size_gb": 25.01,
  "monthly_waste_estimated": 0.50,
  "annual_waste_estimated": 6.00,
  "confidence": "MEDIUM",
  "recommendation": "Add lifecycle policy to abort incomplete uploads after 7 days",
  "lifecycle_rule_example": {
    "action": {"type": "Delete"},
    "condition": {"age": 7}
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_incomplete_multipart_uploads()`

---

### Scénario 5 : Buckets Untagged (Sans Labels)

**Description :** Buckets sans labels (owner, environment, cost-center, etc.). Impossible de tracker ownership et coûts par équipe.

**Impact financier :**
- **Impact indirect :** Confusion attribution coûts
- **Cleanup risqué :** Peur de supprimer = accumulation waste
- **Gouvernance :** Impossible d'enforcer policies

**Logique de détection :**

```python
def detect_cloud_storage_untagged_buckets(
    project_id: str,
    required_labels: list = None
) -> list:
    """
    Détecte les buckets Cloud Storage sans labels obligatoires.

    Args:
        project_id: ID du projet GCP
        required_labels: Liste des labels obligatoires (défaut: ['environment', 'owner'])

    Returns:
        Liste des buckets sans labels
    """
    if required_labels is None:
        required_labels = ['environment', 'owner']

    storage_client = storage.Client(project=project_id)

    untagged_buckets = []

    for bucket in storage_client.list_buckets():
        labels = dict(bucket.labels) if bucket.labels else {}

        # Vérifier labels manquants
        missing_labels = [label for label in required_labels if label not in labels]

        if missing_labels:
            # Bucket untagged

            # Calculer taille bucket pour contexte
            total_size_gb = 0
            object_count = 0

            for blob in bucket.list_blobs(max_results=1000):
                total_size_gb += blob.size / (1024 ** 3)
                object_count += 1

            untagged_buckets.append({
                "bucket_name": bucket.name,
                "location": bucket.location,
                "storage_class": bucket.storage_class,
                "existing_labels": labels,
                "missing_labels": missing_labels,
                "total_size_gb": round(total_size_gb, 2),
                "object_count": object_count,
                "confidence": "HIGH",
                "impact": "Cannot track ownership, costs, or enforce cleanup policies",
                "recommendation": f"Add required labels: {', '.join(missing_labels)}",
            })

    return untagged_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    untagged = detect_cloud_storage_untagged_buckets(
        project_id="my-gcp-project",
        required_labels=['environment', 'owner', 'cost-center']
    )

    print(f"⚠️  {len(untagged)} buckets sans labels obligatoires")

    for bucket in untagged:
        print(f"  - {bucket['bucket_name']}: missing {', '.join(bucket['missing_labels'])}")
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `required_labels` | `['environment', 'owner']` | Labels obligatoires | Ajouter labels = plus strict |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "untagged",
  "bucket_name": "legacy-data-2022",
  "location": "us-central1",
  "storage_class": "STANDARD",
  "existing_labels": {},
  "missing_labels": ["environment", "owner", "cost-center"],
  "total_size_gb": 345.8,
  "object_count": 12450,
  "confidence": "HIGH",
  "impact": "Cannot track ownership, costs, or enforce cleanup policies",
  "recommendation": "Add required labels: environment, owner, cost-center"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_untagged_buckets()`

---

### Scénario 6 : Objects Never Accessed

**Description :** Objects jamais lus (GET) depuis leur création. Possiblement inutiles.

**Impact financier :**
- **Waste mensuel :** $20 - $200/bucket
- **Waste typique :** 20-40% des objects jamais accédés
- **Économie annuelle :** $5K - $20K

**Logique de détection :**

```python
from google.cloud import logging_v2
from collections import defaultdict

def detect_cloud_storage_never_accessed_objects(
    project_id: str,
    bucket_name: str,
    min_age_days: int = 90
) -> list:
    """
    Détecte objects jamais accédés (0 GET) depuis création.

    Nécessite Data Access logs activés.

    Args:
        project_id: ID du projet GCP
        bucket_name: Nom du bucket à analyser
        min_age_days: Âge minimum object (défaut: 90 jours)

    Returns:
        Liste des objects jamais accédés
    """
    storage_client = storage.Client(project=project_id)
    logging_client = logging_v2.Client(project=project_id)

    bucket = storage_client.bucket(bucket_name)

    # 1. Lister tous les objets
    all_objects = {}
    for blob in bucket.list_blobs():
        age_days = (datetime.utcnow().replace(tzinfo=None) - blob.time_created.replace(tzinfo=None)).days

        if age_days >= min_age_days:
            all_objects[blob.name] = {
                "name": blob.name,
                "size_bytes": blob.size,
                "size_gb": blob.size / (1024 ** 3),
                "storage_class": blob.storage_class,
                "time_created": blob.time_created,
                "age_days": age_days
            }

    if not all_objects:
        return []

    # 2. Query Cloud Logging pour storage.objects.get
    filter_str = f'''
    resource.type="gcs_bucket"
    resource.labels.bucket_name="{bucket_name}"
    protoPayload.methodName="storage.objects.get"
    '''

    accessed_objects = set()

    try:
        for entry in logging_client.list_entries(filter_=filter_str, page_size=5000):
            if hasattr(entry.payload, 'resource_name'):
                object_name = entry.payload.resource_name.split('/')[-1]
                accessed_objects.add(object_name)
    except Exception as e:
        print(f"Warning: Could not query access logs: {e}")
        return []

    # 3. Identifier objects jamais accédés
    never_accessed = []

    for obj_name, obj_data in all_objects.items():
        if obj_name not in accessed_objects:
            # Object jamais accédé

            storage_prices = {
                'STANDARD': 0.020,
                'NEARLINE': 0.010,
                'COLDLINE': 0.004,
                'ARCHIVE': 0.0012
            }

            monthly_cost = obj_data["size_gb"] * storage_prices.get(obj_data["storage_class"], 0.020)
            annual_cost = monthly_cost * 12

            # Niveau confiance
            if obj_data["age_days"] >= 365:
                confidence = "CRITICAL"
            elif obj_data["age_days"] >= 180:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            never_accessed.append({
                "bucket_name": bucket_name,
                "object_name": obj_data["name"],
                "size_gb": round(obj_data["size_gb"], 4),
                "storage_class": obj_data["storage_class"],
                "age_days": obj_data["age_days"],
                "time_created": obj_data["time_created"].isoformat(),
                "access_count": 0,
                "monthly_cost": round(monthly_cost, 4),
                "annual_cost": round(annual_cost, 4),
                "confidence": confidence,
                "recommendation": "Consider deleting or archiving unused object",
            })

    return never_accessed


# Exemple d'utilisation
if __name__ == "__main__":
    never_accessed = detect_cloud_storage_never_accessed_objects(
        project_id="my-gcp-project",
        bucket_name="production-data",
        min_age_days=90
    )

    print(f"✅ {len(never_accessed)} objects jamais accédés")

    total_waste = sum([o["annual_cost"] for o in never_accessed])
    print(f"💰 Waste total: ${total_waste:.2f}/an")
```

**Calcul du coût :**

```python
# Object 50 GB jamais accédé (365 jours)
size_gb = 50
storage_class = 'STANDARD'

# Coût storage (facturé depuis 1 an)
monthly_cost = size_gb * 0.020  # $1.00/mois
annual_cost = monthly_cost * 12  # $12.00/an (pur waste)
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_age_days` | 90 jours | Âge minimum object | ↓ = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_object",
  "waste_scenario": "never_accessed",
  "bucket_name": "production-backups",
  "object_name": "legacy-dump-2022-01-15.sql.gz",
  "size_gb": 125.4,
  "storage_class": "STANDARD",
  "age_days": 680,
  "time_created": "2023-01-15T03:00:00Z",
  "access_count": 0,
  "monthly_cost": 2.51,
  "annual_cost": 30.10,
  "confidence": "CRITICAL",
  "recommendation": "Consider deleting or archiving unused object"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_never_accessed_objects()`

---

### Scénario 7 : Lifecycle Policy Absente

**Description :** Buckets sans aucune lifecycle policy pour transition automatique vers storage classes moins chères ou suppression.

**Impact financier :**
- **Surcoût mensuel :** 60-80% (manque d'optimisation)
- **Waste typique :** 50-70% des buckets sans lifecycle
- **Économie annuelle :** $8K - $30K

**Logique de détection :**

```python
def detect_cloud_storage_no_lifecycle_policy(
    project_id: str,
    min_size_gb: float = 10.0
) -> list:
    """
    Détecte buckets sans lifecycle policy (aucune optimisation automatique).

    Args:
        project_id: ID du projet GCP
        min_size_gb: Taille minimum bucket pour considérer (défaut: 10 GB)

    Returns:
        Liste des buckets sans lifecycle policy
    """
    storage_client = storage.Client(project=project_id)

    no_lifecycle_buckets = []

    for bucket in storage_client.list_buckets():
        # Vérifier si lifecycle policy existe
        lifecycle_rules = bucket.lifecycle_rules if bucket.lifecycle_rules else []

        if len(lifecycle_rules) == 0:
            # Aucune lifecycle policy

            # Calculer taille bucket
            total_size_gb = 0
            object_count = 0

            for blob in bucket.list_blobs(max_results=1000):
                total_size_gb += blob.size / (1024 ** 3)
                object_count += 1

            # Filtrer par taille
            if total_size_gb >= min_size_gb:
                # Estimer économie potentielle avec lifecycle
                storage_class = bucket.storage_class or 'STANDARD'

                # Hypothèse: 50% des objects pourraient être en Nearline/Coldline
                current_monthly_cost = total_size_gb * 0.020  # Assume Standard

                # Avec lifecycle optimal: 50% Standard + 30% Nearline + 20% Coldline
                optimal_monthly_cost = (
                    (total_size_gb * 0.50 * 0.020) +  # 50% Standard
                    (total_size_gb * 0.30 * 0.010) +  # 30% Nearline
                    (total_size_gb * 0.20 * 0.004)    # 20% Coldline
                )

                monthly_savings = current_monthly_cost - optimal_monthly_cost
                annual_savings = monthly_savings * 12

                # Niveau confiance
                if total_size_gb > 1000:
                    confidence = "HIGH"
                elif total_size_gb > 100:
                    confidence = "MEDIUM"
                else:
                    confidence = "LOW"

                no_lifecycle_buckets.append({
                    "bucket_name": bucket.name,
                    "location": bucket.location,
                    "storage_class": storage_class,
                    "versioning_enabled": bucket.versioning_enabled,
                    "lifecycle_rules_count": 0,
                    "total_size_gb": round(total_size_gb, 2),
                    "object_count": object_count,
                    "current_monthly_cost": round(current_monthly_cost, 2),
                    "optimal_monthly_cost": round(optimal_monthly_cost, 2),
                    "monthly_savings_potential": round(monthly_savings, 2),
                    "annual_savings_potential": round(annual_savings, 2),
                    "confidence": confidence,
                    "recommendation": "Add lifecycle policy for automatic storage class transitions and deletion",
                    "example_policy": {
                        "rules": [
                            {
                                "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
                                "condition": {"age": 30}
                            },
                            {
                                "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
                                "condition": {"age": 90}
                            },
                            {
                                "action": {"type": "Delete"},
                                "condition": {"age": 365}
                            }
                        ]
                    }
                })

    return no_lifecycle_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    no_lifecycle = detect_cloud_storage_no_lifecycle_policy(
        project_id="my-gcp-project",
        min_size_gb=10.0
    )

    print(f"⚠️  {len(no_lifecycle)} buckets sans lifecycle policy")

    total_savings = sum([b["annual_savings_potential"] for b in no_lifecycle])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Exemple lifecycle policy recommandée :**

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 30
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "COLDLINE"
        },
        "condition": {
          "age": 90
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "ARCHIVE"
        },
        "condition": {
          "age": 365
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 730
        }
      }
    ]
  }
}
```

**Calcul du coût :**

```python
# Bucket 500 GB sans lifecycle (tout en Standard)
total_size_gb = 500

# Coût actuel (100% Standard)
current_monthly_cost = total_size_gb * 0.020  # $10.00/mois

# Coût optimal avec lifecycle
# 50% Standard (accessed frequently)
# 30% Nearline (accessed <1x/mois)
# 20% Coldline (accessed <1x/trimestre)
optimal_monthly_cost = (
    (total_size_gb * 0.50 * 0.020) +  # $5.00
    (total_size_gb * 0.30 * 0.010) +  # $1.50
    (total_size_gb * 0.20 * 0.004)    # $0.40
)  # = $6.90/mois

# Économie
monthly_savings = current_monthly_cost - optimal_monthly_cost  # $3.10/mois
annual_savings = monthly_savings * 12  # $37.20/an (31% économie)
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_size_gb` | 10 GB | Taille minimum bucket | ↓ = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "no_lifecycle_policy",
  "bucket_name": "application-logs-2024",
  "location": "us-central1",
  "storage_class": "STANDARD",
  "versioning_enabled": false,
  "lifecycle_rules_count": 0,
  "total_size_gb": 1250.8,
  "object_count": 45230,
  "current_monthly_cost": 25.02,
  "optimal_monthly_cost": 17.26,
  "monthly_savings_potential": 7.76,
  "annual_savings_potential": 93.07,
  "confidence": "HIGH",
  "recommendation": "Add lifecycle policy for automatic storage class transitions and deletion",
  "example_policy": {
    "rules": [
      {"action": {"type": "SetStorageClass", "storageClass": "NEARLINE"}, "condition": {"age": 30}},
      {"action": {"type": "SetStorageClass", "storageClass": "COLDLINE"}, "condition": {"age": 90}},
      {"action": {"type": "Delete"}, "condition": {"age": 365}}
    ]
  }
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_no_lifecycle_policy()`

---

## Phase 2 : Analyse Avancée (3 Scénarios)

### Scénario 8 : Duplicate Objects (Même Hash MD5/CRC32)

**Description :** Plusieurs objects avec le même contenu (détecté via hash MD5 ou CRC32). Consolidation possible.

**Impact financier :**
- **Waste mensuel :** $50 - $500/bucket
- **Waste typique :** 10-20% de duplication
- **Économie annuelle :** $2K - $15K

**Logique de détection :**

```python
import hashlib
from collections import defaultdict

def detect_cloud_storage_duplicate_objects(
    project_id: str,
    bucket_name: str,
    min_size_gb: float = 0.1
) -> list:
    """
    Détecte objects dupliqués dans un bucket via MD5 hash comparison.

    Args:
        project_id: ID du projet GCP
        bucket_name: Nom du bucket à analyser
        min_size_gb: Taille minimum object pour analyse (défaut: 0.1 GB = 100 MB)

    Returns:
        Groupes d'objects dupliqués
    """
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)

    # Hash → [objects]
    hash_to_objects = defaultdict(list)

    # Lister tous les objets et grouper par hash
    for blob in bucket.list_blobs():
        size_gb = blob.size / (1024 ** 3)

        # Filtrer par taille
        if size_gb < min_size_gb:
            continue

        # Utiliser MD5 hash (fourni par GCS)
        md5_hash = blob.md5_hash

        if md5_hash:
            hash_to_objects[md5_hash].append({
                "name": blob.name,
                "size_gb": size_gb,
                "size_bytes": blob.size,
                "storage_class": blob.storage_class,
                "time_created": blob.time_created,
                "md5_hash": md5_hash
            })

    # Identifier duplicates (hash avec >1 object)
    duplicate_groups = []

    for md5_hash, objects in hash_to_objects.items():
        if len(objects) > 1:
            # Duplicate détecté

            # Calculer waste (tous sauf 1 sont waste)
            size_per_object_gb = objects[0]["size_gb"]
            duplicate_count = len(objects)
            waste_objects_count = duplicate_count - 1
            waste_size_gb = size_per_object_gb * waste_objects_count

            storage_class = objects[0]["storage_class"]
            storage_prices = {
                'STANDARD': 0.020,
                'NEARLINE': 0.010,
                'COLDLINE': 0.004,
                'ARCHIVE': 0.0012
            }

            monthly_waste = waste_size_gb * storage_prices.get(storage_class, 0.020)
            annual_waste = monthly_waste * 12

            # Niveau confiance
            if duplicate_count > 5:
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            duplicate_groups.append({
                "bucket_name": bucket_name,
                "md5_hash": md5_hash,
                "duplicate_count": duplicate_count,
                "size_per_object_gb": round(size_per_object_gb, 4),
                "waste_objects_count": waste_objects_count,
                "waste_size_gb": round(waste_size_gb, 4),
                "storage_class": storage_class,
                "monthly_waste": round(monthly_waste, 4),
                "annual_waste": round(annual_waste, 4),
                "objects": [
                    {
                        "name": obj["name"],
                        "time_created": obj["time_created"].isoformat()
                    }
                    for obj in objects
                ],
                "confidence": confidence,
                "recommendation": f"Keep 1 object, delete {waste_objects_count} duplicates",
            })

    return duplicate_groups


# Exemple d'utilisation
if __name__ == "__main__":
    duplicates = detect_cloud_storage_duplicate_objects(
        project_id="my-gcp-project",
        bucket_name="backup-data",
        min_size_gb=0.1
    )

    print(f"✅ {len(duplicates)} groupes d'objects dupliqués")

    total_waste = sum([g["annual_waste"] for g in duplicates])
    print(f"💰 Waste total: ${total_waste:.2f}/an")

    for group in duplicates:
        print(f"\nHash: {group['md5_hash'][:16]}...")
        print(f"  - {group['duplicate_count']} copies ({group['waste_size_gb']} GB waste)")
        for obj in group['objects']:
            print(f"    • {obj['name']}")
```

**Calcul du coût :**

```python
# 5 copies du même fichier 20 GB (Standard)
size_gb = 20
duplicate_count = 5
waste_count = duplicate_count - 1  # 4 copies = waste

# Waste
waste_size_gb = size_gb * waste_count  # 80 GB
monthly_waste = waste_size_gb * 0.020  # $1.60/mois
annual_waste = monthly_waste * 12  # $19.20/an
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_size_gb` | 0.1 GB | Taille minimum object | ↓ = plus de détections (mais plus lent) |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "duplicate_objects",
  "bucket_name": "user-uploads",
  "md5_hash": "5d41402abc4b2a76b9719d911017c592",
  "duplicate_count": 7,
  "size_per_object_gb": 3.5,
  "waste_objects_count": 6,
  "waste_size_gb": 21.0,
  "storage_class": "STANDARD",
  "monthly_waste": 0.42,
  "annual_waste": 5.04,
  "objects": [
    {"name": "uploads/2023/file1.zip", "time_created": "2023-01-15T10:00:00Z"},
    {"name": "uploads/2023/file1-copy.zip", "time_created": "2023-02-20T14:30:00Z"},
    {"name": "uploads/2024/file1.zip", "time_created": "2024-01-10T09:00:00Z"}
  ],
  "confidence": "HIGH",
  "recommendation": "Keep 1 object, delete 6 duplicates"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_duplicate_objects()`

---

### Scénario 9 : Autoclass Misconfiguration

**Description :** Autoclass désactivé alors que bénéfique (automatise transitions storage class), ou activé sur buckets avec accès fréquent (surcoût operations).

**Impact financier :**
- **Économie potentielle :** $3K - $15K/an
- **Surcoût si mal configuré :** $1K - $5K/an
- **Autoclass cost :** $0.0025/10K operations + $0.0001/GB-mois management fee

**Logique de détection :**

```python
def detect_cloud_storage_autoclass_misconfiguration(
    project_id: str,
    min_size_gb: float = 100.0
) -> list:
    """
    Détecte buckets où Autoclass devrait être activé ou désactivé.

    Autoclass est bénéfique si:
    - Bucket >100 GB
    - Access patterns variables (certains objects hot, d'autres cold)
    - Pas de lifecycle policy existant

    Autoclass est problématique si:
    - Bucket avec accès très fréquent (>1000 ops/jour)
    - Petits buckets (<10 GB) → management fee > économie

    Args:
        project_id: ID du projet GCP
        min_size_gb: Taille minimum pour recommander Autoclass

    Returns:
        Liste des buckets avec Autoclass misconfiguration
    """
    storage_client = storage.Client(project=project_id)

    misconfigured_buckets = []

    for bucket in storage_client.list_buckets():
        # Check Autoclass status
        autoclass_enabled = bucket.autoclass_enabled if hasattr(bucket, 'autoclass_enabled') else False
        autoclass_toggle_time = bucket.autoclass_toggle_time if hasattr(bucket, 'autoclass_toggle_time') else None

        # Calculer taille bucket
        total_size_gb = 0
        object_count = 0

        for blob in bucket.list_blobs(max_results=1000):
            total_size_gb += blob.size / (1024 ** 3)
            object_count += 1

        # Check lifecycle rules
        lifecycle_rules = bucket.lifecycle_rules if bucket.lifecycle_rules else []
        has_storage_class_transitions = any(
            rule.get('action', {}).get('type') == 'SetStorageClass'
            for rule in lifecycle_rules
        )

        # Scénario 1: Autoclass désactivé mais devrait être activé
        if not autoclass_enabled and total_size_gb >= min_size_gb and not has_storage_class_transitions:
            # Bucket large sans optimisation automatique

            # Estimer économie avec Autoclass
            # Hypothèse: 40% des objects peuvent être downgraded
            current_monthly_cost = total_size_gb * 0.020  # Assume Standard

            # Avec Autoclass: 60% Standard + 25% Nearline + 15% Coldline
            autoclass_monthly_cost = (
                (total_size_gb * 0.60 * 0.020) +
                (total_size_gb * 0.25 * 0.010) +
                (total_size_gb * 0.15 * 0.004) +
                (total_size_gb * 0.0001)  # Autoclass management fee
            )

            monthly_savings = current_monthly_cost - autoclass_monthly_cost
            annual_savings = monthly_savings * 12

            if monthly_savings > 5:  # Threshold: >$5/mois économie
                misconfigured_buckets.append({
                    "bucket_name": bucket.name,
                    "location": bucket.location,
                    "storage_class": bucket.storage_class,
                    "autoclass_enabled": False,
                    "should_enable_autoclass": True,
                    "total_size_gb": round(total_size_gb, 2),
                    "lifecycle_rules_count": len(lifecycle_rules),
                    "current_monthly_cost": round(current_monthly_cost, 2),
                    "autoclass_monthly_cost": round(autoclass_monthly_cost, 2),
                    "monthly_savings": round(monthly_savings, 2),
                    "annual_savings": round(annual_savings, 2),
                    "confidence": "HIGH" if total_size_gb > 500 else "MEDIUM",
                    "recommendation": "Enable Autoclass for automatic storage class management",
                })

        # Scénario 2: Autoclass activé mais bucket trop petit
        elif autoclass_enabled and total_size_gb < 10:
            # Bucket petit → management fee > économie

            # Management fee
            management_fee_monthly = total_size_gb * 0.0001

            misconfigured_buckets.append({
                "bucket_name": bucket.name,
                "location": bucket.location,
                "storage_class": bucket.storage_class,
                "autoclass_enabled": True,
                "should_enable_autoclass": False,
                "total_size_gb": round(total_size_gb, 2),
                "autoclass_toggle_time": autoclass_toggle_time.isoformat() if autoclass_toggle_time else None,
                "management_fee_monthly": round(management_fee_monthly, 4),
                "confidence": "MEDIUM",
                "recommendation": "Disable Autoclass (bucket too small, management fee > savings)",
            })

    return misconfigured_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    autoclass_misc = detect_cloud_storage_autoclass_misconfiguration(
        project_id="my-gcp-project",
        min_size_gb=100.0
    )

    print(f"✅ {len(autoclass_misc)} buckets avec Autoclass misconfiguration")

    should_enable = [b for b in autoclass_misc if b.get("should_enable_autoclass")]
    should_disable = [b for b in autoclass_misc if not b.get("should_enable_autoclass")]

    print(f"  - {len(should_enable)} buckets devraient activer Autoclass")
    print(f"  - {len(should_disable)} buckets devraient désactiver Autoclass")

    total_savings = sum([b.get("annual_savings", 0) for b in should_enable])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Calcul du coût :**

```python
# Bucket 500 GB sans Autoclass
total_size_gb = 500

# Coût actuel (100% Standard)
current_monthly_cost = total_size_gb * 0.020  # $10.00/mois

# Avec Autoclass (transitions automatiques)
# 60% Standard + 25% Nearline + 15% Coldline + management fee
autoclass_monthly_cost = (
    (total_size_gb * 0.60 * 0.020) +  # $6.00
    (total_size_gb * 0.25 * 0.010) +  # $1.25
    (total_size_gb * 0.15 * 0.004) +  # $0.30
    (total_size_gb * 0.0001)           # $0.05 management fee
)  # = $7.60/mois

# Économie
monthly_savings = current_monthly_cost - autoclass_monthly_cost  # $2.40/mois
annual_savings = monthly_savings * 12  # $28.80/an (24% économie)
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_size_gb` | 100 GB | Taille minimum pour Autoclass | ↓ = plus de recommandations |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "autoclass_misconfiguration",
  "bucket_name": "analytics-raw-data",
  "location": "us-central1",
  "storage_class": "STANDARD",
  "autoclass_enabled": false,
  "should_enable_autoclass": true,
  "total_size_gb": 1850.3,
  "lifecycle_rules_count": 0,
  "current_monthly_cost": 37.01,
  "autoclass_monthly_cost": 27.94,
  "monthly_savings": 9.07,
  "annual_savings": 108.78,
  "confidence": "HIGH",
  "recommendation": "Enable Autoclass for automatic storage class management"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_autoclass_misconfiguration()`

---

### Scénario 10 : Cross-Region Redundancy Excessive

**Description :** Buckets en multi-region ou dual-region pour données non-critiques. Surcoût 30-100% vs regional.

**Impact financier :**
- **Surcoût mensuel :** 30-100% (multi-region vs region)
- **Waste typique :** 20-40% des buckets sur-redondants
- **Économie annuelle :** $5K - $25K

**Logique de détection :**

```python
def detect_cloud_storage_excessive_redundancy(
    project_id: str,
    min_size_gb: float = 50.0
) -> list:
    """
    Détecte buckets en multi-region/dual-region pour données non-critiques.

    Multi-region est justifié si:
    - Données critiques (99.99% SLA)
    - Traffic global (latency optimization)
    - Disaster recovery requis

    Regional suffit pour:
    - Backups
    - Archives
    - Dev/test data
    - Analytics raw data

    Args:
        project_id: ID du projet GCP
        min_size_gb: Taille minimum pour analyse

    Returns:
        Liste des buckets avec redundancy excessive
    """
    storage_client = storage.Client(project=project_id)

    excessive_redundancy_buckets = []

    for bucket in storage_client.list_buckets():
        location_type = bucket.location_type
        location = bucket.location

        # Filtrer seulement multi-region et dual-region
        if location_type not in ['multi-region', 'dual-region']:
            continue

        # Calculer taille
        total_size_gb = 0
        for blob in bucket.list_blobs(max_results=1000):
            total_size_gb += blob.size / (1024 ** 3)

        if total_size_gb < min_size_gb:
            continue

        # Check labels pour identifier criticality
        labels = dict(bucket.labels) if bucket.labels else {}
        criticality = labels.get('criticality', 'unknown')
        environment = labels.get('environment', 'unknown')

        # Heuristique: si dev/test ou backup → pas besoin multi-region
        is_non_critical = (
            environment in ['dev', 'test', 'staging'] or
            criticality in ['low', 'medium'] or
            'backup' in bucket.name.lower() or
            'archive' in bucket.name.lower() or
            'logs' in bucket.name.lower()
        )

        if is_non_critical or criticality == 'unknown':
            # Calculer surcoût
            storage_class = bucket.storage_class or 'STANDARD'

            # Prix multi-region vs region
            if location_type == 'multi-region':
                # Multi-region pricing
                multi_region_prices = {
                    'STANDARD': 0.026,
                    'NEARLINE': 0.013,
                    'COLDLINE': 0.006,
                    'ARCHIVE': 0.0015
                }
                current_price = multi_region_prices.get(storage_class, 0.026)
            else:  # dual-region
                dual_region_prices = {
                    'STANDARD': 0.024,
                    'NEARLINE': 0.012,
                    'COLDLINE': 0.006,
                    'ARCHIVE': 0.0015
                }
                current_price = dual_region_prices.get(storage_class, 0.024)

            # Prix regional
            regional_prices = {
                'STANDARD': 0.020,
                'NEARLINE': 0.010,
                'COLDLINE': 0.004,
                'ARCHIVE': 0.0012
            }
            optimal_price = regional_prices.get(storage_class, 0.020)

            current_monthly_cost = total_size_gb * current_price
            optimal_monthly_cost = total_size_gb * optimal_price
            monthly_savings = current_monthly_cost - optimal_monthly_cost
            annual_savings = monthly_savings * 12

            # Niveau confiance
            if is_non_critical and criticality != 'unknown':
                confidence = "HIGH"
            else:
                confidence = "MEDIUM"

            excessive_redundancy_buckets.append({
                "bucket_name": bucket.name,
                "location": location,
                "location_type": location_type,
                "storage_class": storage_class,
                "total_size_gb": round(total_size_gb, 2),
                "labels": labels,
                "criticality": criticality,
                "environment": environment,
                "current_price_per_gb": current_price,
                "optimal_price_per_gb": optimal_price,
                "monthly_cost_current": round(current_monthly_cost, 2),
                "monthly_cost_optimal": round(optimal_monthly_cost, 2),
                "monthly_savings": round(monthly_savings, 2),
                "annual_savings": round(annual_savings, 2),
                "savings_pct": round((monthly_savings / current_monthly_cost * 100), 2),
                "confidence": confidence,
                "recommendation": f"Change location from {location_type} to regional (e.g., us-central1)",
            })

    return excessive_redundancy_buckets


# Exemple d'utilisation
if __name__ == "__main__":
    excessive_redundancy = detect_cloud_storage_excessive_redundancy(
        project_id="my-gcp-project",
        min_size_gb=50.0
    )

    print(f"✅ {len(excessive_redundancy)} buckets avec redundancy excessive")

    total_savings = sum([b["annual_savings"] for b in excessive_redundancy])
    print(f"💰 Économie potentielle: ${total_savings:.2f}/an")
```

**Calcul du coût :**

```python
# Bucket 1 TB dev/test en multi-region (Standard)
total_size_gb = 1000

# Coût actuel (multi-region Standard)
current_monthly_cost = total_size_gb * 0.026  # $26.00/mois

# Coût optimal (regional Standard)
optimal_monthly_cost = total_size_gb * 0.020  # $20.00/mois

# Économie
monthly_savings = current_monthly_cost - optimal_monthly_cost  # $6.00/mois
annual_savings = monthly_savings * 12  # $72.00/an (23% économie)
```

**Paramètres configurables :**

| Paramètre | Défaut | Description | Impact si modifié |
|-----------|--------|-------------|-------------------|
| `min_size_gb` | 50 GB | Taille minimum bucket | ↓ = plus de détections |

**Métadonnées :**

```json
{
  "resource_type": "gcp_cloud_storage_bucket",
  "waste_scenario": "excessive_redundancy",
  "bucket_name": "dev-test-data",
  "location": "us",
  "location_type": "multi-region",
  "storage_class": "STANDARD",
  "total_size_gb": 2450.8,
  "labels": {
    "environment": "dev",
    "team": "engineering"
  },
  "criticality": "low",
  "environment": "dev",
  "current_price_per_gb": 0.026,
  "optimal_price_per_gb": 0.020,
  "monthly_cost_current": 63.72,
  "monthly_cost_optimal": 49.02,
  "monthly_savings": 14.70,
  "annual_savings": 176.45,
  "savings_pct": 23.1,
  "confidence": "HIGH",
  "recommendation": "Change location from multi-region to regional (e.g., us-central1)"
}
```

**Implémentation :** `backend/app/providers/gcp.py` → `detect_cloud_storage_excessive_redundancy()`

---

## Protocole de Test Complet

### Tests Unitaires Python

```python
# tests/test_gcp_cloud_storage.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app.providers.gcp import GCPProvider

@pytest.fixture
def gcp_provider():
    """Fixture GCP provider avec credentials mock."""
    return GCPProvider(
        project_id="test-project",
        credentials={
            "type": "service_account",
            "project_id": "test-project",
            "private_key": "mock-key"
        }
    )


class TestCloudStorageEmptyBuckets:
    """Tests scénario 1: Buckets vides."""

    def test_detect_empty_bucket(self, gcp_provider):
        """Test détection bucket vide (0 objets)."""
        with patch('google.cloud.storage.Client') as mock_client:
            # Mock bucket vide
            mock_bucket = Mock()
            mock_bucket.name = "empty-test-bucket"
            mock_bucket.location = "us-central1"
            mock_bucket.location_type = "region"
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.time_created = datetime.utcnow() - timedelta(days=120)
            mock_bucket.versioning_enabled = False
            mock_bucket.lifecycle_rules = []
            mock_bucket.labels = {}

            # Mock list_blobs returning empty
            mock_bucket.list_blobs.return_value = []

            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_empty_buckets(
                age_threshold_days=30
            )

            assert len(results) == 1
            assert results[0]["bucket_name"] == "empty-test-bucket"
            assert results[0]["age_days"] == 120
            assert results[0]["confidence"] == "CRITICAL"  # >90 days

    def test_exclude_young_empty_bucket(self, gcp_provider):
        """Test exclusion bucket vide récent."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = Mock()
            mock_bucket.name = "new-bucket"
            mock_bucket.time_created = datetime.utcnow() - timedelta(days=10)
            mock_bucket.list_blobs.return_value = []

            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_empty_buckets(
                age_threshold_days=30
            )

            assert len(results) == 0  # Excluded (age < threshold)


class TestCloudStorageWrongStorageClass:
    """Tests scénario 2: Wrong storage class."""

    def test_detect_wrong_storage_class(self, gcp_provider):
        """Test détection object Standard non accédé."""
        with patch('google.cloud.storage.Client') as mock_storage:
            with patch('google.cloud.logging_v2.Client') as mock_logging:
                # Mock bucket
                mock_bucket = Mock()
                mock_bucket.name = "data-bucket"

                # Mock object en Standard jamais accédé
                mock_blob = Mock()
                mock_blob.name = "old-file.zip"
                mock_blob.size = 100 * 1024 ** 3  # 100 GB
                mock_blob.storage_class = "STANDARD"
                mock_blob.time_created = datetime.utcnow() - timedelta(days=400)
                mock_blob.updated = datetime.utcnow() - timedelta(days=400)

                mock_bucket.list_blobs.return_value = [mock_blob]
                mock_storage.return_value.bucket.return_value = mock_bucket

                # Mock logs (0 accès)
                mock_logging.return_value.list_entries.return_value = []

                results = gcp_provider.detect_cloud_storage_wrong_storage_class(
                    bucket_name="data-bucket",
                    lookback_days=90
                )

                assert len(results) == 1
                assert results[0]["recommended_storage_class"] == "ARCHIVE"
                assert results[0]["confidence"] == "HIGH"


class TestCloudStorageVersioningWithoutLifecycle:
    """Tests scénario 3: Versioning sans lifecycle."""

    def test_detect_versioning_waste(self, gcp_provider):
        """Test détection versioning sans cleanup policy."""
        with patch('google.cloud.storage.Client') as mock_client:
            # Mock bucket avec versioning enabled
            mock_bucket = Mock()
            mock_bucket.name = "versioned-bucket"
            mock_bucket.versioning_enabled = True
            mock_bucket.lifecycle_rules = []  # Aucune rule
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.location = "us-central1"

            # Mock objects: 100 current + 300 noncurrent versions
            current_blobs = []
            noncurrent_blobs = []

            for i in range(100):
                blob = Mock()
                blob.size = 10 * 1024 ** 3  # 10 GB
                blob.time_deleted = None  # Current
                current_blobs.append(blob)

            for i in range(300):
                blob = Mock()
                blob.size = 10 * 1024 ** 3  # 10 GB
                blob.time_deleted = datetime.utcnow() - timedelta(days=90)
                noncurrent_blobs.append(blob)

            all_blobs = current_blobs + noncurrent_blobs
            mock_bucket.list_blobs.return_value = all_blobs

            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_versioning_without_lifecycle(
                min_noncurrent_versions=10
            )

            assert len(results) == 1
            assert results[0]["noncurrent_versions"] == 300
            assert results[0]["confidence"] == "CRITICAL"


class TestCloudStorageIncompleteUploads:
    """Tests scénario 4: Incomplete multipart uploads."""

    def test_detect_no_abort_policy(self, gcp_provider):
        """Test détection bucket sans abort incomplete policy."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = Mock()
            mock_bucket.name = "upload-bucket"
            mock_bucket.lifecycle_rules = []  # No abort policy
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.location = "us-central1"

            # Mock some objects
            mock_blob = Mock()
            mock_blob.size = 1000 * 1024 ** 3  # 1 TB
            mock_bucket.list_blobs.return_value = [mock_blob]

            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_incomplete_multipart_uploads()

            assert len(results) == 1
            assert results[0]["has_abort_incomplete_policy"] == False


class TestCloudStorageUntagged:
    """Tests scénario 5: Buckets untagged."""

    def test_detect_untagged_buckets(self, gcp_provider):
        """Test détection buckets sans labels obligatoires."""
        with patch('google.cloud.storage.Client') as mock_client:
            # Bucket avec labels partiels
            mock_bucket = Mock()
            mock_bucket.name = "untagged-bucket"
            mock_bucket.location = "us-central1"
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.labels = {"team": "engineering"}  # Manque 'environment' et 'owner'
            mock_bucket.list_blobs.return_value = []

            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_untagged_buckets(
                required_labels=['environment', 'owner', 'cost-center']
            )

            assert len(results) == 1
            assert set(results[0]["missing_labels"]) == {'environment', 'owner', 'cost-center'}
            assert results[0]["confidence"] == "HIGH"


class TestCloudStorageNeverAccessed:
    """Tests scénario 6: Objects never accessed."""

    def test_detect_never_accessed_objects(self, gcp_provider):
        """Test détection objects jamais accédés."""
        with patch('google.cloud.storage.Client') as mock_storage:
            with patch('google.cloud.logging_v2.Client') as mock_logging:
                mock_bucket = Mock()
                mock_bucket.name = "data-bucket"

                # Mock old object
                mock_blob = Mock()
                mock_blob.name = "old-data.csv"
                mock_blob.size = 50 * 1024 ** 3  # 50 GB
                mock_blob.storage_class = "STANDARD"
                mock_blob.time_created = datetime.utcnow() - timedelta(days=400)

                mock_bucket.list_blobs.return_value = [mock_blob]
                mock_storage.return_value.bucket.return_value = mock_bucket

                # Mock logs: no access
                mock_logging.return_value.list_entries.return_value = []

                results = gcp_provider.detect_cloud_storage_never_accessed_objects(
                    bucket_name="data-bucket",
                    min_age_days=90
                )

                assert len(results) == 1
                assert results[0]["access_count"] == 0
                assert results[0]["confidence"] == "CRITICAL"


class TestCloudStorageNoLifecycle:
    """Tests scénario 7: No lifecycle policy."""

    def test_detect_no_lifecycle_policy(self, gcp_provider):
        """Test détection bucket sans lifecycle policy."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = Mock()
            mock_bucket.name = "large-bucket"
            mock_bucket.lifecycle_rules = []  # No lifecycle
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.location = "us-central1"
            mock_bucket.versioning_enabled = False

            # Mock 500 GB bucket
            mock_blobs = []
            for i in range(100):
                blob = Mock()
                blob.size = 5 * 1024 ** 3  # 5 GB each
                mock_blobs.append(blob)

            mock_bucket.list_blobs.return_value = mock_blobs
            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_no_lifecycle_policy(
                min_size_gb=10.0
            )

            assert len(results) == 1
            assert results[0]["lifecycle_rules_count"] == 0
            assert results[0]["confidence"] == "HIGH"


class TestCloudStorageDuplicateObjects:
    """Tests scénario 8: Duplicate objects."""

    def test_detect_duplicate_objects(self, gcp_provider):
        """Test détection objects dupliqués via MD5 hash."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = Mock()
            mock_bucket.name = "uploads"

            # 3 objects avec même hash
            mock_blobs = []
            for i in range(3):
                blob = Mock()
                blob.name = f"file{i}.zip"
                blob.size = 20 * 1024 ** 3  # 20 GB
                blob.storage_class = "STANDARD"
                blob.time_created = datetime.utcnow() - timedelta(days=i*10)
                blob.md5_hash = "abc123def456"  # Same hash
                mock_blobs.append(blob)

            mock_bucket.list_blobs.return_value = mock_blobs
            mock_client.return_value.bucket.return_value = mock_bucket

            results = gcp_provider.detect_cloud_storage_duplicate_objects(
                bucket_name="uploads",
                min_size_gb=0.1
            )

            assert len(results) == 1  # 1 group
            assert results[0]["duplicate_count"] == 3
            assert results[0]["waste_objects_count"] == 2
            assert results[0]["confidence"] == "MEDIUM"


class TestCloudStorageAutoclassMisconfiguration:
    """Tests scénario 9: Autoclass misconfiguration."""

    def test_detect_should_enable_autoclass(self, gcp_provider):
        """Test détection bucket qui devrait activer Autoclass."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = Mock()
            mock_bucket.name = "large-data-bucket"
            mock_bucket.autoclass_enabled = False
            mock_bucket.lifecycle_rules = []
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.location = "us-central1"

            # Mock 500 GB bucket
            mock_blobs = []
            for i in range(100):
                blob = Mock()
                blob.size = 5 * 1024 ** 3  # 5 GB
                mock_blobs.append(blob)

            mock_bucket.list_blobs.return_value = mock_blobs
            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_autoclass_misconfiguration(
                min_size_gb=100.0
            )

            assert len(results) == 1
            assert results[0]["should_enable_autoclass"] == True
            assert results[0]["monthly_savings"] > 0


class TestCloudStorageExcessiveRedundancy:
    """Tests scénario 10: Excessive redundancy."""

    def test_detect_multi_region_dev_bucket(self, gcp_provider):
        """Test détection bucket dev en multi-region."""
        with patch('google.cloud.storage.Client') as mock_client:
            mock_bucket = Mock()
            mock_bucket.name = "dev-test-data"
            mock_bucket.location = "us"
            mock_bucket.location_type = "multi-region"
            mock_bucket.storage_class = "STANDARD"
            mock_bucket.labels = {
                "environment": "dev",
                "criticality": "low"
            }

            # Mock 1 TB bucket
            mock_blobs = []
            for i in range(100):
                blob = Mock()
                blob.size = 10 * 1024 ** 3  # 10 GB
                mock_blobs.append(blob)

            mock_bucket.list_blobs.return_value = mock_blobs
            mock_client.return_value.list_buckets.return_value = [mock_bucket]

            results = gcp_provider.detect_cloud_storage_excessive_redundancy(
                min_size_gb=50.0
            )

            assert len(results) == 1
            assert results[0]["location_type"] == "multi-region"
            assert results[0]["environment"] == "dev"
            assert results[0]["confidence"] == "HIGH"
            assert results[0]["monthly_savings"] > 0
```

### Tests d'Intégration GCP

```bash
# tests/integration/test_gcp_cloud_storage_integration.sh

#!/bin/bash
# Tests d'intégration Cloud Storage sur projet GCP réel

PROJECT_ID="cloudwaste-test"
REGION="us-central1"

echo "🧪 Tests d'intégration GCP Cloud Storage"

# 1. Créer bucket test vide
echo "1️⃣  Créer bucket test vide..."
gsutil mb -c STANDARD -l $REGION gs://test-empty-bucket-$PROJECT_ID/

sleep 5

# 2. Créer bucket test avec objects en mauvaise storage class
echo "2️⃣  Créer bucket test wrong storage class..."
gsutil mb -c STANDARD -l $REGION gs://test-wrong-class-$PROJECT_ID/
echo "test data" | gsutil cp - gs://test-wrong-class-$PROJECT_ID/old-file.txt
# Set object creation time to 1 year ago (via metadata)

sleep 5

# 3. Créer bucket test avec versioning sans lifecycle
echo "3️⃣  Créer bucket test versioning waste..."
gsutil mb -c STANDARD -l $REGION gs://test-versioning-$PROJECT_ID/
gsutil versioning set on gs://test-versioning-$PROJECT_ID/

# Upload multiple versions
for i in {1..5}; do
  echo "version $i" | gsutil cp - gs://test-versioning-$PROJECT_ID/file.txt
done

sleep 5

# 4. Créer bucket test sans labels
echo "4️⃣  Créer bucket test untagged..."
gsutil mb -c STANDARD -l $REGION gs://test-untagged-$PROJECT_ID/
echo "data" | gsutil cp - gs://test-untagged-$PROJECT_ID/file.txt

sleep 5

# 5. Créer bucket test sans lifecycle policy
echo "5️⃣  Créer bucket test no lifecycle..."
gsutil mb -c STANDARD -l $REGION gs://test-no-lifecycle-$PROJECT_ID/

# Upload 100 files
for i in {1..100}; do
  echo "file $i" | gsutil cp - gs://test-no-lifecycle-$PROJECT_ID/file-$i.txt &
done

wait

sleep 5

# 6. Créer bucket test duplicate objects
echo "6️⃣  Créer bucket test duplicates..."
gsutil mb -c STANDARD -l $REGION gs://test-duplicates-$PROJECT_ID/

# Upload same file 3 times with different names
echo "duplicate content" > /tmp/dup.txt
gsutil cp /tmp/dup.txt gs://test-duplicates-$PROJECT_ID/file1.txt
gsutil cp /tmp/dup.txt gs://test-duplicates-$PROJECT_ID/file2.txt
gsutil cp /tmp/dup.txt gs://test-duplicates-$PROJECT_ID/file3.txt

sleep 5

# 7. Créer bucket test multi-region for dev
echo "7️⃣  Créer bucket test multi-region..."
gsutil mb -c STANDARD -l us gs://test-multiregion-dev-$PROJECT_ID/
gsutil label ch -l environment:dev gs://test-multiregion-dev-$PROJECT_ID/

for i in {1..50}; do
  echo "dev data $i" | gsutil cp - gs://test-multiregion-dev-$PROJECT_ID/file-$i.txt &
done

wait

echo "✅ Buckets test créés, attente 2 minutes pour métriques..."
sleep 120

# 8. Exécuter détection CloudWaste
echo "8️⃣  Exécuter détection CloudWaste..."
python -m pytest tests/integration/test_gcp_storage_integration.py -v

# 9. Cleanup
echo "9️⃣  Cleanup buckets test..."
gsutil -m rm -r gs://test-empty-bucket-$PROJECT_ID/ || true
gsutil -m rm -r gs://test-wrong-class-$PROJECT_ID/ || true
gsutil -m rm -r gs://test-versioning-$PROJECT_ID/ || true
gsutil -m rm -r gs://test-untagged-$PROJECT_ID/ || true
gsutil -m rm -r gs://test-no-lifecycle-$PROJECT_ID/ || true
gsutil -m rm -r gs://test-duplicates-$PROJECT_ID/ || true
gsutil -m rm -r gs://test-multiregion-dev-$PROJECT_ID/ || true

echo "✅ Tests d'intégration terminés"
```

### Validation Complète

```python
# tests/integration/test_gcp_storage_integration.py

import pytest
from app.providers.gcp import GCPProvider
from app.core.config import settings

@pytest.fixture
def gcp_provider_integration():
    """Provider GCP avec vraies credentials pour tests intégration."""
    return GCPProvider(
        project_id="cloudwaste-test",
        credentials=settings.GCP_TEST_CREDENTIALS
    )


def test_integration_full_scan(gcp_provider_integration):
    """Test scan complet de tous les buckets avec tous les scénarios."""

    project_id = "cloudwaste-test"

    # Scénario 1: Empty buckets
    empty = gcp_provider_integration.detect_cloud_storage_empty_buckets()
    assert len(empty) >= 1
    assert any(b["bucket_name"].startswith("test-empty-bucket") for b in empty)

    # Scénario 3: Versioning without lifecycle
    versioning = gcp_provider_integration.detect_cloud_storage_versioning_without_lifecycle()
    assert len(versioning) >= 1
    assert any(b["bucket_name"].startswith("test-versioning") for b in versioning)

    # Scénario 5: Untagged
    untagged = gcp_provider_integration.detect_cloud_storage_untagged_buckets(
        required_labels=['environment', 'owner']
    )
    assert len(untagged) >= 1
    assert any(b["bucket_name"].startswith("test-untagged") for b in untagged)

    # Scénario 7: No lifecycle policy
    no_lifecycle = gcp_provider_integration.detect_cloud_storage_no_lifecycle_policy()
    assert len(no_lifecycle) >= 1

    # Scénario 8: Duplicates
    test_bucket = f"test-duplicates-{project_id}"
    duplicates = gcp_provider_integration.detect_cloud_storage_duplicate_objects(
        bucket_name=test_bucket
    )
    assert len(duplicates) >= 1
    assert duplicates[0]["duplicate_count"] == 3

    # Scénario 10: Excessive redundancy
    redundancy = gcp_provider_integration.detect_cloud_storage_excessive_redundancy()
    assert len(redundancy) >= 1

    print("✅ Tous les scénarios détectés correctement")


def test_integration_cost_accuracy(gcp_provider_integration):
    """Test précision des calculs de coût."""

    # Test versioning cost calculation
    versioning = gcp_provider_integration.detect_cloud_storage_versioning_without_lifecycle()

    for bucket in versioning:
        # Vérifier formule pricing
        noncurrent_size_gb = bucket["noncurrent_size_gb"]
        monthly_waste = bucket["monthly_waste"]

        expected_waste = noncurrent_size_gb * 0.020  # Standard pricing

        assert abs(monthly_waste - expected_waste) < 0.01  # Marge 1 cent

    print("✅ Calculs de coût validés")
```

---

## Références

### Documentation Officielle GCP

- **Cloud Storage Overview:** https://cloud.google.com/storage/docs
- **Storage Classes:** https://cloud.google.com/storage/docs/storage-classes
- **Pricing:** https://cloud.google.com/storage/pricing
- **Lifecycle Management:** https://cloud.google.com/storage/docs/lifecycle
- **Autoclass:** https://cloud.google.com/storage/docs/autoclass
- **Versioning:** https://cloud.google.com/storage/docs/object-versioning
- **Best Practices:** https://cloud.google.com/storage/docs/best-practices

### APIs et SDKs

```python
# Python SDK
from google.cloud import storage
from google.cloud import logging_v2

# Storage client
storage_client = storage.Client(project=project_id)

# Bucket operations
bucket = storage_client.bucket(bucket_name)
blobs = bucket.list_blobs()

# Logging client (pour Data Access logs)
logging_client = logging_v2.Client(project=project_id)
```

### gsutil CLI Commands

```bash
# Lister buckets
gsutil ls

# Créer bucket
gsutil mb -c STANDARD -l us-central1 gs://my-bucket/

# Lister objects
gsutil ls gs://my-bucket/

# Lister avec versions
gsutil ls -a gs://my-bucket/

# Get bucket metadata
gsutil ls -L -b gs://my-bucket/

# Set lifecycle policy
gsutil lifecycle set lifecycle.json gs://my-bucket/

# Enable versioning
gsutil versioning set on gs://my-bucket/

# Set storage class
gsutil rewrite -s NEARLINE gs://my-bucket/object.txt

# Add labels
gsutil label set labels.json gs://my-bucket/

# Delete bucket
gsutil rm -r gs://my-bucket/
```

### Lifecycle Policy Examples

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 30,
          "matchesStorageClass": ["STANDARD"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "COLDLINE"
        },
        "condition": {
          "age": 90,
          "matchesStorageClass": ["NEARLINE"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "ARCHIVE"
        },
        "condition": {
          "age": 365,
          "matchesStorageClass": ["COLDLINE"]
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 730
        }
      },
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "daysSinceNoncurrentTime": 30
        }
      }
    ]
  }
}
```

### IAM Permissions Required

```json
{
  "roles/storage.objectViewer": [
    "storage.buckets.get",
    "storage.buckets.list",
    "storage.objects.get",
    "storage.objects.list"
  ],
  "roles/logging.viewer": [
    "logging.logs.list",
    "logging.logEntries.list"
  ]
}
```

**Note importante :** Data Access logging doit être activé pour détecter les accès aux objects :

```bash
# Activer Data Access logs
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member=serviceAccount:SERVICE_ACCOUNT \
  --role=roles/logging.configWriter

# Configurer Data Access logs via Console GCP:
# IAM & Admin → Audit Logs → Cloud Storage → Enable Read
```

### Pricing Calculator

```python
# Calculateur complet Cloud Storage
def calculate_total_storage_cost(
    size_gb: float,
    storage_class: str,
    location_type: str = 'region',
    monthly_class_a_ops: int = 0,
    monthly_class_b_ops: int = 0,
    monthly_retrieval_gb: float = 0,
    monthly_egress_gb: float = 0
) -> dict:
    """
    Calcule coût total Cloud Storage.

    Returns:
        Dict avec breakdown des coûts
    """
    # Storage pricing
    storage_prices = {
        'region': {
            'STANDARD': 0.020,
            'NEARLINE': 0.010,
            'COLDLINE': 0.004,
            'ARCHIVE': 0.0012
        },
        'dual-region': {
            'STANDARD': 0.024,
            'NEARLINE': 0.012,
            'COLDLINE': 0.006,
            'ARCHIVE': 0.0015
        },
        'multi-region': {
            'STANDARD': 0.026,
            'NEARLINE': 0.013,
            'COLDLINE': 0.006,
            'ARCHIVE': 0.0015
        }
    }

    storage_cost = size_gb * storage_prices[location_type][storage_class]

    # Operations
    class_a_cost = (monthly_class_a_ops / 10_000) * 0.05
    class_b_cost = (monthly_class_b_ops / 10_000) * 0.004

    # Retrieval
    retrieval_prices = {
        'STANDARD': 0,
        'NEARLINE': 0.01,
        'COLDLINE': 0.02,
        'ARCHIVE': 0.05
    }
    retrieval_cost = monthly_retrieval_gb * retrieval_prices[storage_class]

    # Egress
    egress_cost = monthly_egress_gb * 0.12

    total = storage_cost + class_a_cost + class_b_cost + retrieval_cost + egress_cost

    return {
        'storage_cost': storage_cost,
        'class_a_ops_cost': class_a_cost,
        'class_b_ops_cost': class_b_cost,
        'retrieval_cost': retrieval_cost,
        'egress_cost': egress_cost,
        'total_monthly_cost': total
    }


# Exemple
costs = calculate_total_storage_cost(
    size_gb=1000,
    storage_class='STANDARD',
    location_type='region',
    monthly_class_a_ops=100_000,
    monthly_class_b_ops=1_000_000,
    monthly_egress_gb=100
)

print(f"Storage: ${costs['storage_cost']:.2f}")
print(f"Operations: ${costs['class_a_ops_cost'] + costs['class_b_ops_cost']:.2f}")
print(f"Egress: ${costs['egress_cost']:.2f}")
print(f"Total: ${costs['total_monthly_cost']:.2f}/mois")
```

### Best Practices Summary

1. **Storage Classes** : Utiliser lifecycle policies pour transitions automatiques
2. **Versioning** : Toujours avec lifecycle policy (delete old versions après 30 jours)
3. **Lifecycle Policies** : Obligatoire pour buckets >10 GB
4. **Autoclass** : Activer pour buckets >100 GB sans lifecycle custom
5. **Labels** : Toujours ajouter `environment`, `owner`, `cost-center`
6. **Location Type** : Regional pour dev/test, multi-region seulement si global traffic
7. **Data Access Logs** : Activer pour monitoring accès (coût minimal)
8. **Incomplete Uploads** : Lifecycle policy pour abort après 7 jours

---

**Document Version:** 1.0
**Date:** 2025-01-03
**Auteur:** CloudWaste Team
**Statut:** ✅ Complete
