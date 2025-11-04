# CloudWaste - Couverture 100% GCP BigQuery

**Resource Type:** `Analytics : BigQuery`
**Provider:** Google Cloud Platform (GCP)
**API:** `bigquery.googleapis.com` (BigQuery API v2)
**Équivalents:** AWS Redshift, Azure Synapse Analytics, Snowflake
**Total Scenarios:** 10 (100% coverage)

---

## 📋 Table des Matières

- [Vue d'Ensemble](#vue-densemble)
- [Modèle de Pricing BigQuery](#modèle-de-pricing-bigquery)
- [Phase 1 - Détection Simple (7 scénarios)](#phase-1---détection-simple-7-scénarios)
  - [1. Tables Jamais Interrogées](#1-bigquery_never_queried_tables---tables-jamais-interrogées)
  - [2. Active Storage Waste](#2-bigquery_active_storage_waste---active-storage-should-be-long-term)
  - [3. Datasets Vides](#3-bigquery_empty_datasets---datasets-vides)
  - [4. Tables Sans Expiration](#4-bigquery_no_expiration---tables-sans-expiration)
  - [5. Tables >1 TB Sans Partitioning](#5-bigquery_unpartitioned_large_tables---tables-1-tb-sans-partitioning)
  - [6. Tables >100 GB Sans Clustering](#6-bigquery_unclustered_large_tables---tables-100-gb-sans-clustering)
  - [7. Datasets Non Tagués](#7-bigquery_untagged_datasets---datasets-non-tagués)
- [Phase 2 - Détection Avancée (3 scénarios)](#phase-2---détection-avancée-3-scénarios)
  - [8. Queries Scanning >10 TB](#8-bigquery_expensive_queries---queries-scanning-10-tb)
  - [9. On-Demand vs Flat-Rate Optimization](#9-bigquery_ondemand_vs_flatrate---on-demand-vs-flat-rate-optimization)
  - [10. Materialized Views Non Utilisées](#10-bigquery_unused_materialized_views---materialized-views-non-utilisées)
- [Protocole de Test](#protocole-de-test)
- [Références](#références)

---

## Vue d'Ensemble

### Contexte BigQuery

**BigQuery** est le data warehouse **serverless** de GCP, offrant :

- **Serverless** (aucune infrastructure à gérer)
- **Separation storage/compute** (scaling indépendant)
- **SQL standard** (ANSI SQL 2011)
- **Pétabyte-scale** (jusqu'à pétabytes de données)
- **Sub-second queries** (queries sur TB en secondes)
- **Machine Learning** (BigQuery ML intégré)

### Architecture BigQuery

```
Organization
├── Project 1
│   ├── Dataset A (region: us-central1)
│   │   ├── Table 1 (partitioned, clustered)
│   │   ├── Table 2 (non-partitioned)
│   │   └── Materialized View 1
│   └── Dataset B (region: eu-west1)
│       └── Tables...
└── Project 2
    └── Datasets...
```

### Caractéristiques Principales

| Feature | Description | Impact Coût |
|---------|-------------|-------------|
| **Storage** | Active vs Long-term (automatic) | $0.020 vs $0.010/GB/mo |
| **Queries** | On-demand (pay-per-query) | $5/TB scanned |
| **Flat-Rate** | Slots réservés (100-500+) | $2,000-10,000+/mois |
| **Partitioning** | Par date/temps/integer/range | -90% query costs |
| **Clustering** | Par colonnes (jusqu'à 4) | -50% query costs |
| **Streaming** | Real-time inserts | $0.010/200 MB |
| **BigQuery ML** | Machine learning intégré | Storage + training costs |

### Storage Tiers

| Type | Prix/GB/Mois | Condition | Transition |
|------|-------------|-----------|-----------|
| **Active** | $0.020 | Données modifiées <90 jours | Automatique |
| **Long-term** | $0.010 | Données non modifiées 90+ jours | Automatique après 90j |

**Note :** Transition automatique vers long-term après 90 jours sans modification → **50% économie**

### Query Pricing Models

#### On-Demand (Pay-per-Query)
- **$5/TB** scanned (après 1 TB gratuit/mois par projet)
- Facturation au MB près (minimum 10 MB par table)
- Pas de coût fixe

#### Flat-Rate (Slots Réservés)
- **$2,000/mois** pour 100 slots (engagement mensuel)
- **$1,700/mois** pour 100 slots (engagement annuel = -15%)
- Queries illimitées (pas de frais par TB)

### Waste Typique

1. **Tables jamais interrogées** : 100 TB × $0.020/mois = $2,000/mois storage waste
2. **Active storage pour old data** : 50% surcoût vs long-term ($0.020 vs $0.010)
3. **Queries non optimisées** : Full table scans = 10 TB × $5 = $50 par query
4. **Unpartitioned tables** : Scans 10x+ plus de données que nécessaire
5. **On-demand pour usage prévisible** : $3,000/mois vs $2,000/mois flat-rate = $1,000/mois waste
6. **Temporary tables sans expiration** : Accumulation storage +10-20%/mois
7. **Materialized views unused** : Storage + refresh compute waste

---

## Modèle de Pricing BigQuery

### Storage Pricing

#### Active Storage
```
Prix: $0.020/GB/mois
Condition: Données modifiées dans les 90 derniers jours
```

**Exemples :**
- 1 TB active : 1,000 GB × $0.020 = **$20/mois**
- 10 TB active : 10,000 GB × $0.020 = **$200/mois**
- 100 TB active : 100,000 GB × $0.020 = **$2,000/mois**

#### Long-term Storage
```
Prix: $0.010/GB/mois
Condition: Données non modifiées pendant 90+ jours
Transition: Automatique
```

**Exemples :**
- 1 TB long-term : 1,000 GB × $0.010 = **$10/mois** (-50%)
- 10 TB long-term : 10,000 GB × $0.010 = **$100/mois** (-50%)
- 100 TB long-term : 100,000 GB × $0.010 = **$1,000/mois** (-50%)

#### Logical Storage vs Physical Storage

BigQuery facture le **logical storage** (uncompressed), mais stocke les données compressées (physical). La compression moyenne est 3-5x.

---

### Query Pricing

#### On-Demand Pricing

```
Prix: $5/TB scanned (après 1 TB gratuit/mois)
Facturation: Au MB près (minimum 10 MB par table)
```

**Exemples queries :**

| Query Description | Bytes Scanned | Cost |
|-------------------|---------------|------|
| `SELECT * FROM table` (1 GB) | 1 GB | $0.005 |
| Full table scan (100 GB) | 100 GB | $0.50 |
| Unpartitioned table (1 TB) | 1 TB | $5.00 |
| Unoptimized query (10 TB) | 10 TB | $50.00 |
| Daily scheduled query (5 TB/jour) | 150 TB/mois | $750.00/mois |

#### Flat-Rate Pricing

| Plan | Slots | Prix Mensuel | Prix Annuel (−15%) | Break-Even |
|------|-------|-------------|-------------------|-----------|
| **Baseline** | 100 | $2,000/mois | $1,700/mois | 400 TB/mois |
| **Standard** | 500 | $10,000/mois | $8,500/mois | 2,000 TB/mois |
| **Enterprise** | 2000 | $40,000/mois | $34,000/mois | 8,000 TB/mois |

**Règle générale :** Flat-rate recommandé si query costs on-demand > $2,000/mois

---

### Exemples Coûts Mensuels

#### Scénario 1 : Startup Analytics (Data Warehouse Simple)

```
Storage:
- Active: 5 TB × $0.020 = $100
- Long-term: 15 TB × $0.010 = $150

Queries (on-demand):
- 50 TB scanned/mois × $5 = $250

Total: $500/mois (~$6,000/an)
```

#### Scénario 2 : PME Data Platform (Usage Modéré)

```
Storage:
- Active: 50 TB × $0.020 = $1,000
- Long-term: 200 TB × $0.010 = $2,000

Queries (on-demand):
- 500 TB scanned/mois × $5 = $2,500

Total: $5,500/mois (~$66,000/an)

Recommandation: Flat-rate 100 slots ($2,000/mois) = économie $500/mois
Avec flat-rate: $1,000 + $2,000 + $2,000 = $5,000/mois (~$60,000/an)
```

#### Scénario 3 : Entreprise Data Lake (Usage Intensif)

```
Storage:
- Active: 100 TB × $0.020 = $2,000
- Long-term: 500 TB × $0.010 = $5,000

Queries (flat-rate 500 slots):
- Unlimited queries = $10,000

Total: $17,000/mois (~$204,000/an)

Si on-demand: queries = 3,000 TB × $5 = $15,000/mois
Économie flat-rate: $15,000 - $10,000 = $5,000/mois (~$60,000/an)
```

#### Scénario 4 : Waste Typique (Avant CloudWaste)

```
Storage:
- Active: 150 TB (dont 100 TB never queried) × $0.020 = $3,000
- Long-term: 50 TB × $0.010 = $500

Queries (on-demand):
- 1,000 TB scanned/mois (unoptimized) × $5 = $5,000
- Dont 60% avoidable avec partitioning/clustering

Total: $8,500/mois (~$102,000/an)
Waste: ~$4,500/mois (~$54,000/an)
```

---

## Phase 1 - Détection Simple (7 scénarios)

### 1. `bigquery_never_queried_tables` - Tables Jamais Interrogées

#### Détection

**Logique :**
```python
# 1. Lister toutes les tables dans le projet
from google.cloud import bigquery

client = bigquery.Client(project=project_id)

# 2. Query INFORMATION_SCHEMA.TABLES pour table metadata
query_tables = f"""
SELECT
  table_catalog,
  table_schema,
  table_name,
  creation_time,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), creation_time, DAY) as age_days,
  size_bytes / POW(1024, 3) as size_gb,
  row_count,
  type
FROM `{project_id}.INFORMATION_SCHEMA.TABLES`
WHERE table_type = 'BASE TABLE'
  AND creation_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
ORDER BY size_bytes DESC
"""

tables = list(client.query(query_tables).result())

# 3. Pour chaque table, vérifier si queries existent (30 jours)
for table in tables:
    table_fqn = f"{table.table_catalog}.{table.table_schema}.{table.table_name}"

    # Query INFORMATION_SCHEMA.JOBS_BY_PROJECT pour query history
    query_jobs = f"""
    SELECT COUNT(*) as query_count
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
      AND state = 'DONE'
      AND error_result IS NULL
      AND ARRAY_LENGTH(referenced_tables) > 0
      AND EXISTS (
        SELECT 1 FROM UNNEST(referenced_tables) as ref
        WHERE ref.table_id = '{table.table_name}'
          AND ref.dataset_id = '{table.table_schema}'
      )
    """

    result = list(client.query(query_jobs).result())
    query_count = result[0].query_count if result else 0

    # 4. Détection si 0 queries
    if query_count == 0 and table.size_gb >= min_size_gb:
        # Table jamais interrogée = 100% storage waste
```

**Critères :**
- `creation_time < now() - 90 days`
- `query_count == 0` dans `JOBS_BY_PROJECT` (90 jours)
- `size_bytes >= 1 GB` (ignorer tiny tables)
- `type = 'BASE TABLE'` (pas views)

**API Calls :**
```python
# BigQuery API
from google.cloud import bigquery

client = bigquery.Client()

# INFORMATION_SCHEMA queries
tables_query = "SELECT * FROM `project.INFORMATION_SCHEMA.TABLES`"
jobs_query = "SELECT * FROM `project.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`"
```

#### Calcul de Coût

**Formule :**

Table jamais interrogée = 100% storage waste :

```python
# Récupérer storage tier (active ou long-term)
age_days = (now - table.creation_time).days

# Si table modifiée dans 90 derniers jours → active
# Sinon → long-term (automatic transition)

if age_days < 90:
    storage_price = 0.020  # $/GB/mois
else:
    storage_price = 0.010  # $/GB/mois (long-term)

size_gb = table.size_bytes / (1024**3)

# Coût mensuel = 100% waste (table jamais utilisée)
monthly_cost = size_gb * storage_price

# Coût gaspillé depuis création
age_months = age_days / 30.0
already_wasted = monthly_cost * age_months
```

**Exemple :**

Table 10 TB jamais interrogée depuis 180 jours :
```python
size_gb = 10000
age_days = 180
storage_price = 0.010  # long-term (>90 days)

monthly_cost = 10000 * 0.010 = $100/mois
already_wasted = $100 * (180/30) = $600
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `never_queried_days` | int | 90 | Période sans queries pour détection |
| `min_size_gb` | float | 1.0 | Taille minimum table (ignorer tiny tables) |
| `exclude_datasets` | list | `['logs', 'temp']` | Datasets à exclure |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:dataset.table_never_queried",
  "resource_name": "old_analytics_data",
  "resource_type": "bigquery_never_queried_tables",
  "project_id": "my-project-123",
  "dataset_id": "analytics",
  "table_id": "old_analytics_data",
  "location": "us-central1",
  "creation_time": "2024-02-15T10:00:00Z",
  "age_days": 260,
  "size_bytes": 10737418240000,
  "size_gb": 10000.0,
  "row_count": 500000000,
  "storage_tier": "long_term",
  "query_count_90d": 0,
  "last_query_date": null,
  "estimated_monthly_cost": 100.00,
  "already_wasted": 866.67,
  "confidence": "high",
  "recommendation": "Delete table or export to Cloud Storage Coldline ($0.004/GB = 60% savings)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 2. `bigquery_active_storage_waste` - Active Storage Should Be Long-term

#### Détection

**Logique :**
```python
# 1. Lister tables avec last_modified_time >90 jours
query = f"""
SELECT
  table_catalog,
  table_schema,
  table_name,
  creation_time,
  COALESCE(
    (SELECT MAX(last_modified_time)
     FROM `{project_id}.{dataset_id}.__TABLES__` t
     WHERE t.table_id = TABLES.table_name),
    creation_time
  ) as last_modified_time,
  TIMESTAMP_DIFF(
    CURRENT_TIMESTAMP(),
    COALESCE(last_modified_time, creation_time),
    DAY
  ) as days_since_modified,
  size_bytes / POW(1024, 3) as size_gb
FROM `{project_id}.INFORMATION_SCHEMA.TABLES`
WHERE table_type = 'BASE TABLE'
  AND TIMESTAMP_DIFF(
        CURRENT_TIMESTAMP(),
        COALESCE(last_modified_time, creation_time),
        DAY
      ) >= 90
ORDER BY size_bytes DESC
"""

tables = list(client.query(query).result())

# 2. Vérifier storage billing tier
# Note: BigQuery transition automatique après 90 jours
# MAIS si table recemment modifiée puis abandonnée = reste en active

for table in tables:
    # Calculer économie si migration manuelle vers long-term
    # (via export/reimport ou table copy)

    if table.days_since_modified >= 90 and table.size_gb >= 1.0:
        # Active storage waste = devrait être long-term
        waste = table.size_gb * (0.020 - 0.010)  # $0.010/GB/mois économie
```

**Critères :**
- `last_modified_time < now() - 90 days`
- Table toujours en **active storage tier** (billing)
- Pas de queries récentes (table dormante)

**API Calls :**
```python
# BigQuery API
client.query("SELECT * FROM `project.INFORMATION_SCHEMA.TABLES`")
client.query("SELECT * FROM `project.dataset.__TABLES__`")  # Metadata table
```

#### Calcul de Coût

**Formule :**

Active storage → Long-term = -50% coût :

```python
# Table >90 jours sans modification devrait être long-term

size_gb = table.size_bytes / (1024**3)

# Coût actuel (active)
current_cost = size_gb * 0.020

# Coût recommandé (long-term)
recommended_cost = size_gb * 0.010

# Waste = différence
monthly_waste = current_cost - recommended_cost

# Économie annuelle
annual_savings = monthly_waste * 12
```

**Exemple :**

Table 50 TB sans modification depuis 120 jours :
```python
size_gb = 50000
days_since_modified = 120

current_cost = 50000 * 0.020 = $1,000/mois
recommended_cost = 50000 * 0.010 = $500/mois
monthly_waste = $500
annual_savings = $500 * 12 = $6,000/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `days_since_modified_threshold` | int | 90 | Jours sans modification pour long-term |
| `min_size_gb` | float | 1.0 | Taille minimum table |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:dataset.old_events",
  "resource_name": "old_events",
  "resource_type": "bigquery_active_storage_waste",
  "project_id": "my-project-123",
  "dataset_id": "analytics",
  "table_id": "old_events",
  "creation_time": "2023-05-01T00:00:00Z",
  "last_modified_time": "2024-05-15T10:30:00Z",
  "days_since_modified": 171,
  "size_gb": 50000.0,
  "storage_tier": "active",
  "current_cost_monthly": 1000.00,
  "recommended_storage_tier": "long_term",
  "recommended_cost_monthly": 500.00,
  "estimated_monthly_waste": 500.00,
  "annual_savings": 6000.00,
  "confidence": "high",
  "recommendation": "Table not modified in 171 days - should transition to long-term storage (automatic after 90d)",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 3. `bigquery_empty_datasets` - Datasets Vides

#### Détection

**Logique :**
```python
# 1. Lister tous les datasets dans le projet
datasets = list(client.list_datasets(project=project_id))

# 2. Pour chaque dataset, compter tables
for dataset in datasets:
    dataset_ref = client.dataset(dataset.dataset_id, project=project_id)

    # Query INFORMATION_SCHEMA pour count tables
    query = f"""
    SELECT COUNT(*) as table_count
    FROM `{project_id}.{dataset.dataset_id}.INFORMATION_SCHEMA.TABLES`
    """

    result = list(client.query(query).result())
    table_count = result[0].table_count if result else 0

    # 3. Détection si 0 tables
    if table_count == 0:
        # Dataset vide = governance waste

        # Vérifier âge dataset
        age_days = (datetime.utcnow() - dataset.created).days

        if age_days >= min_age_days:
            # Dataset vide depuis longtemps = waste détecté
```

**Critères :**
- `table_count == 0` dans dataset
- `age_days >= 30` (éviter faux positifs nouveaux datasets)

**API Calls :**
```python
# BigQuery API
client.list_datasets(project=project_id)
client.query("SELECT COUNT(*) FROM `project.dataset.INFORMATION_SCHEMA.TABLES`")
```

#### Calcul de Coût

**Formule :**

Dataset vide = coût minimal mais indicateur de waste :

```python
# Datasets vides n'ont pas de storage cost
# MAIS indicateur de:
# - Projets abandonnés
# - Mauvaise gouvernance
# - Potentiel autres wastes dans le projet

# Coût estimé = overhead governance
governance_waste = 0  # Pas de coût direct

# Mais peut indiquer projet avec autre wastes
# → Trigger scan complet du projet
```

**Exemple :**

Dataset vide depuis 180 jours :
```python
table_count = 0
age_days = 180

# Pas de coût storage direct
monthly_cost = 0

# Recommandation: supprimer dataset
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_age_days` | int | 30 | Âge minimum dataset pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:old_analytics",
  "resource_name": "old_analytics",
  "resource_type": "bigquery_empty_datasets",
  "project_id": "my-project-123",
  "dataset_id": "old_analytics",
  "location": "us-central1",
  "creation_time": "2024-04-15T08:00:00Z",
  "age_days": 201,
  "table_count": 0,
  "estimated_monthly_cost": 0.00,
  "confidence": "medium",
  "recommendation": "Delete empty dataset - likely abandoned project",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 4. `bigquery_no_expiration` - Tables Sans Expiration

#### Détection

**Logique :**
```python
# 1. Identifier tables temporaires (naming patterns)
temp_patterns = [
    '%temp%', '%tmp%', '%staging%', '%stg%',
    '%test%', '%scratch%', '%backup%'
]

# 2. Query tables matching temp patterns
query = f"""
SELECT
  table_catalog,
  table_schema,
  table_name,
  creation_time,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), creation_time, DAY) as age_days,
  size_bytes / POW(1024, 3) as size_gb,
  ddl
FROM `{project_id}.INFORMATION_SCHEMA.TABLES`
WHERE table_type = 'BASE TABLE'
  AND (
    LOWER(table_name) LIKE '%temp%' OR
    LOWER(table_name) LIKE '%tmp%' OR
    LOWER(table_name) LIKE '%staging%' OR
    LOWER(table_schema) LIKE '%temp%'
  )
ORDER BY size_bytes DESC
"""

tables = list(client.query(query).result())

# 3. Pour chaque table, vérifier expiration
for table in tables:
    table_ref = client.get_table(f"{table.table_catalog}.{table.table_schema}.{table.table_name}")

    # 4. Détection si pas d'expiration configurée
    if table_ref.expires is None:
        # Table temporaire sans expiration = accumulation waste

        # Calculer coût accumulation
        age_months = table.age_days / 30.0
        storage_cost = table.size_gb * 0.020 * age_months
```

**Critères :**
- Table name/dataset matches temp patterns
- `expires = null` (aucune expiration configurée)
- `age_days >= 7` (tables temporaires devraient être de courte durée)

**API Calls :**
```python
# BigQuery API
client.query("SELECT * FROM `project.INFORMATION_SCHEMA.TABLES`")
table_ref = client.get_table("project.dataset.table")
print(table_ref.expires)  # None ou datetime
```

#### Calcul de Coût

**Formule :**

Tables temporaires sans expiration = accumulation :

```python
# Tables temporaires devraient avoir expiration (7-30 jours)
# Sans expiration → accumulation continue

size_gb = table.size_bytes / (1024**3)
age_days = (now - table.creation_time).days

# Hypothèse: table aurait dû être supprimée après 30 jours
intended_lifetime_days = 30

if age_days > intended_lifetime_days:
    # Coût waste = coût depuis 30 jours
    waste_days = age_days - intended_lifetime_days
    waste_months = waste_days / 30.0

    monthly_cost = size_gb * 0.020
    already_wasted = monthly_cost * waste_months
else:
    # Pas encore waste, mais potentiel futur waste
    monthly_cost = size_gb * 0.020
    already_wasted = 0
```

**Exemple :**

Table staging 5 TB sans expiration depuis 180 jours :
```python
size_gb = 5000
age_days = 180
intended_lifetime_days = 30

waste_days = 180 - 30 = 150
waste_months = 150 / 30 = 5

monthly_cost = 5000 * 0.020 = $100/mois
already_wasted = $100 * 5 = $500
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `temp_name_patterns` | list | `['temp', 'tmp', 'staging']` | Patterns pour tables temporaires |
| `intended_lifetime_days` | int | 30 | Durée vie attendue tables temp |
| `min_age_days` | int | 7 | Âge minimum pour détection |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:dataset.temp_staging_data",
  "resource_name": "temp_staging_data",
  "resource_type": "bigquery_no_expiration",
  "project_id": "my-project-123",
  "dataset_id": "staging",
  "table_id": "temp_staging_data",
  "creation_time": "2024-05-05T14:00:00Z",
  "age_days": 181,
  "size_gb": 5000.0,
  "expires": null,
  "intended_lifetime_days": 30,
  "excess_days": 151,
  "estimated_monthly_cost": 100.00,
  "already_wasted": 503.33,
  "confidence": "high",
  "recommendation": "Set table expiration to 30 days for temporary/staging tables",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 5. `bigquery_unpartitioned_large_tables` - Tables >1 TB Sans Partitioning

#### Détection

**Logique :**
```python
# 1. Query tables >1 TB sans partitioning
query = f"""
SELECT
  table_catalog,
  table_schema,
  table_name,
  size_bytes / POW(1024, 4) as size_tb,
  row_count,
  creation_time
FROM `{project_id}.INFORMATION_SCHEMA.TABLES`
WHERE table_type = 'BASE TABLE'
  AND size_bytes > 1099511627776  -- 1 TB
  AND (
    -- Not partitioned
    ddl NOT LIKE '%PARTITION BY%'
    OR ddl IS NULL
  )
ORDER BY size_bytes DESC
"""

tables = list(client.query(query).result())

# 2. Pour chaque table, analyser queries récentes (30 jours)
for table in tables:
    # Query JOBS_BY_PROJECT pour analyser scan patterns
    query_jobs = f"""
    SELECT
      COUNT(*) as query_count,
      AVG(total_bytes_processed / POW(1024, 4)) as avg_tb_scanned,
      SUM(total_bytes_processed / POW(1024, 4)) as total_tb_scanned
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND state = 'DONE'
      AND error_result IS NULL
      AND EXISTS (
        SELECT 1 FROM UNNEST(referenced_tables) as ref
        WHERE ref.table_id = '{table.table_name}'
      )
    """

    result = list(client.query(query_jobs).result())

    if result and result[0].query_count > 0:
        # 3. Calculer coût queries
        total_tb_scanned = result[0].total_tb_scanned
        query_cost_30d = total_tb_scanned * 5  # $5/TB

        # 4. Détection si full table scans coûteux
        if result[0].avg_tb_scanned > (table.size_tb * 0.5):
            # Queries scannent >50% de la table
            # → Partitioning réduirait coût de 90%
            potential_savings = query_cost_30d * 0.90
```

**Critères :**
- `size_bytes > 1 TB`
- Pas de `PARTITION BY` dans DDL
- Queries récentes scannent >50% table (full scans)

**API Calls :**
```python
# BigQuery API
client.query("SELECT * FROM `project.INFORMATION_SCHEMA.TABLES`")
client.query("SELECT * FROM `project.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`")
```

#### Calcul de Coût

**Formule :**

Unpartitioned table → Partitioned = -90% query costs :

```python
# Table 10 TB sans partitioning
# Queries font full table scans

size_tb = 10
queries_per_month = 100

# Coût actuel (full scans)
current_scan_per_query = size_tb  # Full table scan
current_cost_per_query = current_scan_per_query * 5  # $5/TB
current_monthly_cost = current_cost_per_query * queries_per_month

# Coût recommandé (partitioned)
# Hypothèse: partitioning réduit scan de 90%
recommended_scan_per_query = size_tb * 0.10  # 10% scan
recommended_cost_per_query = recommended_scan_per_query * 5
recommended_monthly_cost = recommended_cost_per_query * queries_per_month

# Waste
monthly_waste = current_monthly_cost - recommended_monthly_cost
savings_percentage = 90  # Typical avec bon partitioning
```

**Exemple :**

Table 10 TB unpartitioned, 100 queries/mois (full scans) :
```python
size_tb = 10
queries_per_month = 100

current_cost = 10 * 5 * 100 = $5,000/mois
recommended_cost = (10 * 0.10) * 5 * 100 = $500/mois
monthly_waste = $4,500
annual_savings = $4,500 * 12 = $54,000/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_size_tb` | float | 1.0 | Taille minimum pour détection |
| `full_scan_threshold` | float | 0.5 | % table scannée pour considérer full scan |
| `estimated_partition_reduction` | float | 0.90 | % réduction scan attendue avec partitioning |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:dataset.large_events",
  "resource_name": "large_events",
  "resource_type": "bigquery_unpartitioned_large_tables",
  "project_id": "my-project-123",
  "dataset_id": "analytics",
  "table_id": "large_events",
  "size_tb": 10.5,
  "row_count": 5000000000,
  "is_partitioned": false,
  "query_metrics_30d": {
    "query_count": 120,
    "avg_tb_scanned": 9.8,
    "total_tb_scanned": 1176.0
  },
  "current_query_cost_monthly": 5880.00,
  "recommended_partitioning": "PARTITION BY DATE(timestamp)",
  "estimated_scan_reduction": 90,
  "recommended_query_cost_monthly": 588.00,
  "estimated_monthly_waste": 5292.00,
  "annual_savings": 63504.00,
  "confidence": "high",
  "recommendation": "Add date partitioning - 90% query cost reduction expected",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 6. `bigquery_unclustered_large_tables` - Tables >100 GB Sans Clustering

#### Détection

**Logique :**
```python
# 1. Query tables >100 GB sans clustering
query = f"""
SELECT
  table_catalog,
  table_schema,
  table_name,
  size_bytes / POW(1024, 3) as size_gb,
  row_count,
  ddl
FROM `{project_id}.INFORMATION_SCHEMA.TABLES`
WHERE table_type = 'BASE TABLE'
  AND size_bytes > 107374182400  -- 100 GB
  AND (
    -- Not clustered
    ddl NOT LIKE '%CLUSTER BY%'
    OR ddl IS NULL
  )
ORDER BY size_bytes DESC
"""

tables = list(client.query(query).result())

# 2. Analyser query patterns pour identifier clustering opportunities
for table in tables:
    # Query JOBS pour analyser WHERE clauses communes
    query_jobs = f"""
    SELECT
      query,
      total_bytes_processed / POW(1024, 3) as gb_scanned
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND state = 'DONE'
      AND EXISTS (
        SELECT 1 FROM UNNEST(referenced_tables) as ref
        WHERE ref.table_id = '{table.table_name}'
      )
    LIMIT 100
    """

    jobs = list(client.query(query_jobs).result())

    # 3. Analyser WHERE clauses pour identifier colonnes filtrées
    # Exemple: WHERE user_id = X AND country = Y
    # → Recommander CLUSTER BY (user_id, country)

    common_filter_columns = analyze_where_clauses(jobs)

    if common_filter_columns:
        # 4. Calculer économie potentielle (clustering = -30-50% scan)
        avg_scan_gb = sum([j.gb_scanned for j in jobs]) / len(jobs) if jobs else 0
        estimated_reduction = 0.40  # 40% reduction typical
        potential_savings = (avg_scan_gb * estimated_reduction * 5) * len(jobs)
```

**Critères :**
- `size_bytes > 100 GB`
- Pas de `CLUSTER BY` dans DDL
- Queries avec WHERE clauses communes sur certaines colonnes

**API Calls :**
```python
# BigQuery API
client.query("SELECT * FROM `project.INFORMATION_SCHEMA.TABLES`")
client.query("SELECT query FROM `project.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`")
```

#### Calcul de Coût

**Formule :**

Unclustered table → Clustered = -30-50% query costs :

```python
# Table 500 GB sans clustering
# Queries avec filters sur colonnes spécifiques

size_gb = 500
queries_per_month = 200
avg_scan_gb_per_query = 300  # Scan 60% table

# Coût actuel (unclustered)
current_cost_per_query = avg_scan_gb_per_query / 1000 * 5  # $/TB
current_monthly_cost = current_cost_per_query * queries_per_month

# Coût recommandé (clustered)
# Clustering réduit scan de 40% typical
clustering_reduction = 0.40
recommended_scan_gb = avg_scan_gb_per_query * (1 - clustering_reduction)
recommended_cost_per_query = recommended_scan_gb / 1000 * 5
recommended_monthly_cost = recommended_cost_per_query * queries_per_month

# Waste
monthly_waste = current_monthly_cost - recommended_monthly_cost
```

**Exemple :**

Table 500 GB unclustered, 200 queries/mois :
```python
size_gb = 500
queries_per_month = 200
avg_scan_gb = 300

current_cost = (300 / 1000 * 5) * 200 = $300/mois
recommended_cost = ((300 * 0.60) / 1000 * 5) * 200 = $180/mois
monthly_waste = $120
annual_savings = $120 * 12 = $1,440/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `min_size_gb` | float | 100.0 | Taille minimum table |
| `clustering_reduction` | float | 0.40 | % réduction scan avec clustering |
| `min_queries_per_month` | int | 10 | Queries minimum pour recommandation |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:dataset.user_events",
  "resource_name": "user_events",
  "resource_type": "bigquery_unclustered_large_tables",
  "project_id": "my-project-123",
  "dataset_id": "analytics",
  "table_id": "user_events",
  "size_gb": 500.0,
  "is_clustered": false,
  "query_metrics_30d": {
    "query_count": 200,
    "avg_gb_scanned": 300.0
  },
  "common_filter_columns": ["user_id", "country", "event_date"],
  "recommended_clustering": "CLUSTER BY user_id, country",
  "estimated_scan_reduction": 40,
  "current_query_cost_monthly": 300.00,
  "recommended_query_cost_monthly": 180.00,
  "estimated_monthly_waste": 120.00,
  "annual_savings": 1440.00,
  "confidence": "high",
  "recommendation": "Add clustering on user_id, country - 40% query cost reduction expected",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 7. `bigquery_untagged_datasets` - Datasets Non Tagués

#### Détection

**Logique :**
```python
# 1. Lister tous les datasets
datasets = list(client.list_datasets(project=project_id))

# 2. Définir labels requis (configurables)
required_labels = ['environment', 'owner', 'cost-center', 'project']

# 3. Pour chaque dataset, vérifier labels
for dataset_ref in datasets:
    dataset = client.get_dataset(dataset_ref.reference)

    labels = dataset.labels if dataset.labels else {}

    # 4. Identifier labels manquants
    missing_labels = [label for label in required_labels if label not in labels]

    # 5. Détection si labels manquants
    if missing_labels:
        # Untagged dataset = governance waste

        # Calculer coût total dataset (storage + queries)
        dataset_cost = calculate_dataset_cost(dataset)

        # Governance waste = 5% du coût
        governance_waste = dataset_cost * 0.05
```

**Critères :**
- Labels manquants parmi la liste requise
- Dataset actif (non vide)

**API Calls :**
```python
# BigQuery API
datasets = client.list_datasets(project=project_id)
dataset = client.get_dataset(dataset_ref)
print(dataset.labels)  # Dict ou None
```

#### Calcul de Coût

**Formule :**

Coût de gouvernance (estimé) :

```python
# Datasets non tagués = perte visibilité coûts
# Coût estimé = 5% du coût total dataset

# 1. Calculer storage cost
query_storage = f"""
SELECT SUM(size_bytes) / POW(1024, 3) as total_size_gb
FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
"""

result = list(client.query(query_storage).result())
total_size_gb = result[0].total_size_gb if result else 0

storage_cost = total_size_gb * 0.020  # Hypothèse: active storage

# 2. Estimer query cost (30 derniers jours)
query_jobs = f"""
SELECT SUM(total_bytes_processed) / POW(1024, 4) as total_tb_scanned
FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND state = 'DONE'
  AND EXISTS (
    SELECT 1 FROM UNNEST(referenced_tables) as ref
    WHERE ref.dataset_id = '{dataset_id}'
  )
"""

result_jobs = list(client.query(query_jobs).result())
total_tb_scanned = result_jobs[0].total_tb_scanned if result_jobs else 0

query_cost = total_tb_scanned * 5

# Total dataset cost
total_monthly_cost = storage_cost + query_cost

# Governance waste = 5%
governance_waste_pct = 0.05
monthly_waste = total_monthly_cost * governance_waste_pct
```

**Exemple :**

Dataset 10 TB storage + $1,000 queries/mois, sans labels :
```python
storage_cost = 10000 * 0.020 = $200
query_cost = $1,000
total_monthly_cost = $1,200

governance_waste = $1,200 * 0.05 = $60/mois
annual_waste = $60 * 12 = $720/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `required_labels` | list | `['environment', 'owner', 'cost-center']` | Labels requis |
| `governance_waste_pct` | float | 0.05 | % coût attribué au waste gouvernance |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:analytics",
  "resource_name": "analytics",
  "resource_type": "bigquery_untagged_datasets",
  "project_id": "my-project-123",
  "dataset_id": "analytics",
  "location": "us-central1",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center", "project"],
  "storage_size_gb": 10000.0,
  "storage_cost_monthly": 200.00,
  "query_cost_monthly": 1000.00,
  "total_monthly_cost": 1200.00,
  "estimated_monthly_waste": 60.00,
  "annual_waste": 720.00,
  "confidence": "medium",
  "recommendation": "Add required labels for cost allocation and governance",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

## Phase 2 - Détection Avancée (3 scénarios)

### 8. `bigquery_expensive_queries` - Queries Scanning >10 TB

#### Détection

**Logique :**

Analyser queries coûteuses et recommander optimisations :

```python
# 1. Query INFORMATION_SCHEMA.JOBS_BY_PROJECT pour queries >10 TB
query = f"""
SELECT
  job_id,
  user_email,
  query,
  creation_time,
  total_bytes_processed / POW(1024, 4) as tb_scanned,
  (total_bytes_processed / POW(1024, 4)) * 5 as cost_usd,
  referenced_tables,
  total_slot_ms,
  statement_type
FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND state = 'DONE'
  AND error_result IS NULL
  AND total_bytes_processed > 10995116277760  -- 10 TB
ORDER BY total_bytes_processed DESC
LIMIT 100
"""

expensive_queries = list(client.query(query).result())

# 2. Pour chaque expensive query, analyser causes
for job in expensive_queries:
    # 3. Identifier problèmes communs:
    # - SELECT * (all columns)
    # - No WHERE clause
    # - No partitioning filter
    # - JOINS without filters
    # - Suboptimal query structure

    issues = []

    if 'SELECT *' in job.query.upper():
        issues.append('select_star')

    if 'WHERE' not in job.query.upper():
        issues.append('no_where_clause')

    # 4. Calculer coût si query est scheduled (répétée)
    # Check si c'est scheduled query
    if 'scheduled_query' in job.job_id:
        # Query répétée quotidiennement
        daily_runs = 1  # Hypothèse
        monthly_cost = job.cost_usd * daily_runs * 30

        # Si monthly cost >$1,000 → critical optimization needed
```

**Critères :**
- `total_bytes_processed > 10 TB` par query
- État = DONE (success)
- Query récurrente (scheduled) = coût multiplié

**API Calls :**
```python
# BigQuery API
query = "SELECT * FROM `project.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`"
client.query(query)
```

#### Calcul de Coût

**Formule :**

Query >10 TB = $50+ par exécution :

```python
# Query scanning 15 TB
tb_scanned = 15.0

# Coût par query
cost_per_query = tb_scanned * 5  # $5/TB

# Si scheduled query (daily)
runs_per_month = 30
monthly_cost = cost_per_query * runs_per_month

# Optimisation potentielle
# Hypothèse: avec optimizations → réduction 70% scan
optimization_reduction = 0.70

optimized_tb_scanned = tb_scanned * (1 - optimization_reduction)
optimized_cost_per_query = optimized_tb_scanned * 5
optimized_monthly_cost = optimized_cost_per_query * runs_per_month

# Waste
monthly_waste = monthly_cost - optimized_monthly_cost
```

**Exemple :**

Query scanning 15 TB, scheduled daily :
```python
tb_scanned = 15.0
runs_per_month = 30

current_cost = 15 * 5 * 30 = $2,250/mois
optimized_cost = (15 * 0.30) * 5 * 30 = $675/mois
monthly_waste = $1,575
annual_savings = $1,575 * 12 = $18,900/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `expensive_query_tb_threshold` | float | 10.0 | TB scanned minimum |
| `lookback_days` | int | 30 | Période analyse queries |
| `optimization_reduction` | float | 0.70 | % réduction attendue avec optimizations |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:job_abc123",
  "resource_name": "scheduled_analytics_query",
  "resource_type": "bigquery_expensive_queries",
  "project_id": "my-project-123",
  "job_id": "scheduled_query_abc123",
  "user_email": "data-team@company.com",
  "query_preview": "SELECT * FROM large_table JOIN other_table...",
  "creation_time": "2024-11-01T10:00:00Z",
  "tb_scanned": 15.3,
  "cost_per_run": 76.50,
  "is_scheduled": true,
  "runs_per_month": 30,
  "current_monthly_cost": 2295.00,
  "issues_detected": ["select_star", "no_where_clause", "unpartitioned_table_scan"],
  "optimization_recommendations": [
    "Replace SELECT * with specific columns",
    "Add WHERE clause with date filter",
    "Use partitioned table version"
  ],
  "estimated_optimized_monthly_cost": 688.50,
  "estimated_monthly_waste": 1606.50,
  "annual_savings": 19278.00,
  "confidence": "high",
  "recommendation": "Optimize query - 70% cost reduction possible with partitioning and column selection",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 9. `bigquery_ondemand_vs_flatrate` - On-Demand vs Flat-Rate Optimization

#### Détection

**Logique :**

Analyser coûts queries mensuels et recommander flat-rate si applicable :

```python
# 1. Calculer total query costs (30 derniers jours)
query = f"""
SELECT
  SUM(total_bytes_processed) / POW(1024, 4) as total_tb_scanned,
  COUNT(*) as total_queries,
  AVG(total_bytes_processed) / POW(1024, 3) as avg_gb_per_query
FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND state = 'DONE'
  AND error_result IS NULL
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'  -- Exclude scripts
"""

result = list(client.query(query).result())[0]

total_tb_scanned = result.total_tb_scanned
total_queries = result.total_queries

# 2. Calculer on-demand cost
# Note: 1 TB gratuit/mois par projet
free_tb = 1.0
billable_tb = max(0, total_tb_scanned - free_tb)
ondemand_monthly_cost = billable_tb * 5  # $5/TB

# 3. Calculer flat-rate cost
# Flat-rate: $2,000/mois pour 100 slots (ou $1,700 avec annual)
flatrate_monthly_cost = 2000  # Baseline 100 slots

# 4. Détection si on-demand > flat-rate
if ondemand_monthly_cost > flatrate_monthly_cost:
    # Flat-rate recommandé

    # Calculer économie
    monthly_savings = ondemand_monthly_cost - flatrate_monthly_cost
    savings_percentage = (monthly_savings / ondemand_monthly_cost) * 100

    # Vérifier si workload est prévisible (pas de spike)
    # Analyser variance quotidienne
    daily_variance = calculate_daily_query_variance()

    if daily_variance < 0.30:  # Variance <30% = workload stable
        # Flat-rate strongly recommended
        confidence = 'high'
    else:
        # Workload variable, flat-rate maybe not optimal
        confidence = 'medium'
```

**Critères :**
- `ondemand_monthly_cost > $2,000`
- Workload relativement stable (variance <30%)
- Queries prévisibles (pas de spike ponctuel)

**API Calls :**
```python
# BigQuery API
query = "SELECT * FROM `project.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`"
client.query(query)
```

#### Calcul de Coût

**Formule :**

On-demand vs Flat-rate comparison :

```python
# Analyser 30 derniers jours
total_tb_scanned = 650  # TB scanned in 30 days
free_tb = 1.0  # 1 TB gratuit/mois

# On-demand cost
billable_tb = total_tb_scanned - free_tb
ondemand_monthly_cost = billable_tb * 5

# Flat-rate cost (100 slots)
flatrate_monthly_cost = 2000  # Mensuel
# OU
flatrate_annual_cost = 1700  # Avec engagement annuel (-15%)

# Économie
monthly_savings = ondemand_monthly_cost - flatrate_monthly_cost
annual_savings = monthly_savings * 12

# Si engagement annuel
annual_savings_with_commitment = (ondemand_monthly_cost - flatrate_annual_cost) * 12
```

**Exemple :**

Projet avec 650 TB queries/mois :
```python
total_tb_scanned = 650
free_tb = 1

ondemand_cost = (650 - 1) * 5 = $3,245/mois
flatrate_cost = $2,000/mois (mensuel) OU $1,700/mois (annuel)

monthly_savings = $3,245 - $2,000 = $1,245
annual_savings = $1,245 * 12 = $14,940/an

# Avec engagement annuel
monthly_savings_annual = $3,245 - $1,700 = $1,545
annual_savings_annual = $1,545 * 12 = $18,540/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `flatrate_baseline_cost` | float | 2000.0 | Coût flat-rate 100 slots/mois |
| `flatrate_annual_cost` | float | 1700.0 | Coût avec engagement annuel |
| `min_savings_threshold` | float | 300.0 | Économie min pour recommendation |
| `max_variance_threshold` | float | 0.30 | Variance max workload pour high confidence |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:pricing_analysis",
  "resource_name": "project_pricing_optimization",
  "resource_type": "bigquery_ondemand_vs_flatrate",
  "project_id": "my-project-123",
  "analysis_period_days": 30,
  "query_metrics": {
    "total_queries": 15000,
    "total_tb_scanned": 650.0,
    "avg_tb_per_day": 21.7,
    "daily_variance": 0.18
  },
  "current_pricing_model": "on_demand",
  "current_monthly_cost": 3245.00,
  "recommended_pricing_model": "flat_rate",
  "flatrate_monthly_cost": 2000.00,
  "flatrate_annual_cost": 1700.00,
  "estimated_monthly_savings": 1245.00,
  "estimated_annual_savings": 14940.00,
  "savings_percentage": 38.4,
  "workload_stability": "high",
  "confidence": "high",
  "recommendation": "Switch to flat-rate pricing (100 slots) - 38% cost reduction with stable workload",
  "detection_date": "2024-11-02T14:30:00Z"
}
```

#### Fichier d'Implémentation

**Backend :** `/backend/app/providers/gcp.py` (à implémenter)

---

### 10. `bigquery_unused_materialized_views` - Materialized Views Non Utilisées

#### Détection

**Logique :**

Identifier materialized views créées mais jamais interrogées :

```python
# 1. Lister toutes les materialized views
query_mvs = f"""
SELECT
  table_catalog,
  table_schema,
  table_name,
  creation_time,
  size_bytes / POW(1024, 3) as size_gb,
  ddl
FROM `{project_id}.INFORMATION_SCHEMA.TABLES`
WHERE table_type = 'MATERIALIZED_VIEW'
ORDER BY size_bytes DESC
"""

materialized_views = list(client.query(query_mvs).result())

# 2. Pour chaque materialized view, vérifier usage (30 jours)
for mv in materialized_views:
    # Query JOBS pour queries référençant la MV
    query_usage = f"""
    SELECT COUNT(*) as query_count
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND state = 'DONE'
      AND error_result IS NULL
      AND EXISTS (
        SELECT 1 FROM UNNEST(referenced_tables) as ref
        WHERE ref.table_id = '{mv.table_name}'
          AND ref.dataset_id = '{mv.table_schema}'
      )
    """

    result = list(client.query(query_usage).result())
    query_count = result[0].query_count if result else 0

    # 3. Détection si 0 queries
    if query_count == 0:
        # Materialized view jamais utilisée = waste

        # Calculer coût storage + refresh
        storage_cost = mv.size_gb * 0.020

        # Estimer refresh cost (approximation)
        # MV refresh = query coût base table
        # Hypothèse: refresh daily, scan 10% base table
        base_table_size_gb = estimate_base_table_size(mv)
        refresh_tb = (base_table_size_gb / 1000) * 0.10
        refresh_cost_per_day = refresh_tb * 5
        refresh_cost_monthly = refresh_cost_per_day * 30

        total_monthly_waste = storage_cost + refresh_cost_monthly
```

**Critères :**
- `table_type = 'MATERIALIZED_VIEW'`
- `query_count == 0` dans 30 derniers jours
- MV active (pas disabled)

**API Calls :**
```python
# BigQuery API
query = "SELECT * FROM `project.INFORMATION_SCHEMA.TABLES` WHERE table_type = 'MATERIALIZED_VIEW'"
client.query(query)
```

#### Calcul de Coût

**Formule :**

Materialized view unused = storage + refresh waste :

```python
# MV size: 500 GB
# Base table: 5 TB
# Refresh: daily, scans 10% base table

size_gb = 500
base_table_size_tb = 5.0

# Storage cost
storage_cost = size_gb * 0.020

# Refresh cost
# Refresh scans 10% base table daily
refresh_tb_per_day = base_table_size_tb * 0.10
refresh_cost_per_day = refresh_tb_per_day * 5
refresh_cost_monthly = refresh_cost_per_day * 30

# Total waste
monthly_waste = storage_cost + refresh_cost_monthly
```

**Exemple :**

MV 500 GB sur base table 5 TB, refresh daily :
```python
size_gb = 500
base_table_size_tb = 5.0

storage_cost = 500 * 0.020 = $10/mois
refresh_cost = (5 * 0.10 * 5) * 30 = $75/mois
monthly_waste = $10 + $75 = $85/mois
annual_waste = $85 * 12 = $1,020/an
```

#### Paramètres Configurables

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `lookback_days` | int | 30 | Période sans usage pour détection |
| `refresh_scan_percentage` | float | 0.10 | % base table scannée au refresh |

#### Métadonnées Exemple

```json
{
  "resource_id": "project-123:dataset.mv_user_summary",
  "resource_name": "mv_user_summary",
  "resource_type": "bigquery_unused_materialized_views",
  "project_id": "my-project-123",
  "dataset_id": "analytics",
  "table_id": "mv_user_summary",
  "creation_time": "2024-07-10T08:00:00Z",
  "size_gb": 500.0,
  "base_table": "analytics.user_events",
  "base_table_size_tb": 5.0,
  "query_count_30d": 0,
  "refresh_frequency": "daily",
  "storage_cost_monthly": 10.00,
  "refresh_cost_monthly": 75.00,
  "estimated_monthly_waste": 85.00,
  "annual_waste": 1020.00,
  "confidence": "high",
  "recommendation": "Delete unused materialized view or investigate why not being queried",
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
gcloud services enable bigquery.googleapis.com
gcloud services enable bigquerystorage.googleapis.com
```

#### 2. Service Account

```bash
# Ajouter permissions BigQuery
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:cloudwaste-scanner@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloudwaste-key.json"
```

#### 3. Installer bq CLI

```bash
# bq CLI inclus avec gcloud SDK
bq version

# Configuration
bq init
```

---

### Tests Unitaires - Créer Ressources Test

#### Scénario 1: Table Never Queried

```bash
# Créer dataset
bq mk --dataset \
  --location=us-central1 \
  --description="Test dataset for CloudWaste" \
  ${PROJECT_ID}:test_waste_detection

# Créer table never queried (large)
bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_waste_detection.never_queried_table \
  'SELECT
     GENERATE_UUID() as id,
     CAST(FLOOR(RAND() * 1000000) AS INT64) as user_id,
     CURRENT_TIMESTAMP() as created_at,
     REPEAT("x", 1000) as large_text
   FROM UNNEST(GENERATE_ARRAY(1, 1000000)) as num'

# Vérifier taille
bq show --format=prettyjson ${PROJECT_ID}:test_waste_detection.never_queried_table \
  | grep numBytes

# Attendre 90 jours (ou backdater creation_time pour test)
# Note: Pour test rapide, modifier detection threshold à 1 jour
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_never_queried_tables",
  "size_gb": ">1",
  "query_count_90d": 0,
  "estimated_monthly_cost": ">= 20"
}
```

---

#### Scénario 2: Active Storage Waste

```bash
# Créer table old (simuler table >90 jours sans modification)
bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_waste_detection.old_active_table \
  'SELECT * FROM `bigquery-public-data.usa_names.usa_1910_current` LIMIT 100000'

# Simuler age: backdater last_modified_time (impossible via bq)
# Alternative: créer table il y a 90+ jours et ne jamais modifier
# Pour test: ajuster threshold detection à 7 jours
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_active_storage_waste",
  "days_since_modified": ">= 90",
  "storage_tier": "active",
  "estimated_monthly_waste": ">= 10"
}
```

---

#### Scénario 3: Empty Dataset

```bash
# Créer dataset vide
bq mk --dataset \
  --location=us-central1 \
  --description="Empty test dataset" \
  ${PROJECT_ID}:test_empty_dataset

# Ne créer AUCUNE table

# Attendre 30 jours (ou ajuster threshold)
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_empty_datasets",
  "table_count": 0,
  "age_days": ">= 30"
}
```

---

#### Scénario 4: Tables Sans Expiration

```bash
# Créer temporary table SANS expiration
bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_waste_detection.temp_staging_table \
  'SELECT * FROM UNNEST(GENERATE_ARRAY(1, 10000)) as id'

# Vérifier pas d'expiration
bq show ${PROJECT_ID}:test_waste_detection.temp_staging_table \
  | grep expirationTime
# Devrait être vide

# Attendre 7+ jours
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_no_expiration",
  "table_name": "temp_staging_table",
  "expires": null,
  "age_days": ">= 7"
}
```

---

#### Scénario 5: Unpartitioned Large Table

```bash
# Créer large table (>1 TB) SANS partitioning
# Note: Difficile de créer 1 TB pour test
# Alternative: réduire threshold à 100 GB pour test

bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_waste_detection.large_unpartitioned \
  'SELECT
     date,
     name,
     state,
     number,
     REPEAT("x", 10000) as large_field
   FROM `bigquery-public-data.usa_names.usa_1910_current`'

# Faire quelques queries avec full table scans
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) FROM `'${PROJECT_ID}'.test_waste_detection.large_unpartitioned`'

bq query --use_legacy_sql=false \
  'SELECT * FROM `'${PROJECT_ID}'.test_waste_detection.large_unpartitioned` LIMIT 10'
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_unpartitioned_large_tables",
  "size_tb": ">= 1",
  "is_partitioned": false,
  "query_count": "> 0",
  "estimated_monthly_waste": ">= 100"
}
```

---

#### Scénario 6: Unclustered Large Table

```bash
# Créer table >100 GB SANS clustering
bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_waste_detection.large_unclustered \
  'SELECT
     *,
     REPEAT("x", 5000) as padding
   FROM `bigquery-public-data.usa_names.usa_1910_current`'

# Queries avec WHERE clause sur colonnes communes
bq query --use_legacy_sql=false \
  'SELECT * FROM `'${PROJECT_ID}'.test_waste_detection.large_unclustered`
   WHERE state = "CA" LIMIT 100'

bq query --use_legacy_sql=false \
  'SELECT * FROM `'${PROJECT_ID}'.test_waste_detection.large_unclustered`
   WHERE name = "John" LIMIT 100'
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_unclustered_large_tables",
  "size_gb": ">= 100",
  "is_clustered": false,
  "common_filter_columns": ["state", "name"],
  "estimated_monthly_waste": ">= 50"
}
```

---

#### Scénario 7: Untagged Dataset

```bash
# Créer dataset SANS labels
bq mk --dataset \
  --location=us-central1 \
  ${PROJECT_ID}:test_untagged_dataset

# Créer table dedans
bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_untagged_dataset.some_table \
  'SELECT * FROM UNNEST(GENERATE_ARRAY(1, 10000)) as id'
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_untagged_datasets",
  "labels": {},
  "missing_labels": ["environment", "owner", "cost-center"]
}
```

---

#### Scénario 8: Expensive Queries

```bash
# Créer scheduled query qui scan >10 TB
# Note: Difficile de créer 10 TB pour test
# Alternative: ajuster threshold à 100 GB

# Créer table large
bq query --use_legacy_sql=false \
  --destination_table=${PROJECT_ID}:test_waste_detection.large_table \
  'SELECT
     *,
     REPEAT("x", 20000) as padding
   FROM `bigquery-public-data.usa_names.usa_1910_current`'

# Query qui fait full scan (expensive)
bq query --use_legacy_sql=false \
  'SELECT COUNT(*), AVG(number)
   FROM `'${PROJECT_ID}'.test_waste_detection.large_table`'

# Vérifier bytes processed
bq show -j [JOB_ID]
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_expensive_queries",
  "tb_scanned": ">= 10",
  "cost_per_run": ">= 50",
  "issues_detected": ["select_star", "no_where_clause"]
}
```

---

#### Scénario 9: On-Demand vs Flat-Rate

```bash
# Générer volume queries >400 TB/mois
# Note: Coûteux pour test
# Alternative: analyser projet réel avec historique

# Script Python pour simuler analyse
python3 << 'EOF'
from google.cloud import bigquery

client = bigquery.Client()

query = f"""
SELECT
  SUM(total_bytes_processed) / POW(1024, 4) as total_tb,
  (SUM(total_bytes_processed) / POW(1024, 4)) * 5 as ondemand_cost
FROM `{PROJECT_ID}.region-us-central1.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND state = 'DONE'
"""

result = list(client.query(query).result())[0]
print(f"Total TB scanned: {result.total_tb}")
print(f"On-demand cost: ${result.ondemand_cost}")
print(f"Flat-rate cost: $2,000")
print(f"Savings: ${result.ondemand_cost - 2000}")
EOF
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_ondemand_vs_flatrate",
  "current_monthly_cost": ">= 2000",
  "flatrate_monthly_cost": 2000,
  "estimated_monthly_savings": ">= 300"
}
```

---

#### Scénario 10: Unused Materialized Views

```bash
# Créer materialized view
bq query --use_legacy_sql=false \
  'CREATE MATERIALIZED VIEW `'${PROJECT_ID}'.test_waste_detection.mv_user_summary`
   AS
   SELECT
     state,
     COUNT(*) as name_count,
     SUM(number) as total_number
   FROM `bigquery-public-data.usa_names.usa_1910_current`
   GROUP BY state'

# Vérifier MV créée
bq show ${PROJECT_ID}:test_waste_detection.mv_user_summary

# NE PAS interroger la MV (laisser unused)

# Attendre 30 jours (ou ajuster threshold à 7 jours)
```

**Validation attendue :**
```json
{
  "resource_type": "bigquery_unused_materialized_views",
  "query_count_30d": 0,
  "storage_cost_monthly": ">= 1",
  "refresh_cost_monthly": ">= 1"
}
```

---

### Validation Globale

#### Script Test Complet

```python
#!/usr/bin/env python3
"""
Script validation BigQuery waste detection
"""

from google.cloud import bigquery
import os

PROJECT_ID = os.environ['PROJECT_ID']

def test_all_scenarios():
    client = bigquery.Client(project=PROJECT_ID)

    scenarios_detected = {
        'never_queried_tables': 0,
        'active_storage_waste': 0,
        'empty_datasets': 0,
        'no_expiration': 0,
        'unpartitioned_large_tables': 0,
        'unclustered_large_tables': 0,
        'untagged_datasets': 0,
        'expensive_queries': 0,
        'ondemand_vs_flatrate': 0,
        'unused_materialized_views': 0,
    }

    # Test 1: Never queried tables
    query_tables = f"""
    SELECT COUNT(*) as count
    FROM `{PROJECT_ID}.INFORMATION_SCHEMA.TABLES`
    WHERE table_type = 'BASE TABLE'
      AND creation_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
    """
    result = list(client.query(query_tables).result())[0]
    scenarios_detected['never_queried_tables'] = result.count
    print(f"✅ Scenario 1 (never queried): {result.count} tables")

    # Test 3: Empty datasets
    datasets = list(client.list_datasets(project=PROJECT_ID))
    for dataset in datasets:
        query_count = f"""
        SELECT COUNT(*) as count
        FROM `{PROJECT_ID}.{dataset.dataset_id}.INFORMATION_SCHEMA.TABLES`
        """
        result = list(client.query(query_count).result())[0]
        if result.count == 0:
            scenarios_detected['empty_datasets'] += 1

    print(f"✅ Scenario 3 (empty datasets): {scenarios_detected['empty_datasets']} datasets")

    # Test 5: Unpartitioned large tables
    query_unpart = f"""
    SELECT COUNT(*) as count
    FROM `{PROJECT_ID}.INFORMATION_SCHEMA.TABLES`
    WHERE table_type = 'BASE TABLE'
      AND size_bytes > 107374182400  -- 100 GB
      AND (ddl NOT LIKE '%PARTITION BY%' OR ddl IS NULL)
    """
    result = list(client.query(query_unpart).result())[0]
    scenarios_detected['unpartitioned_large_tables'] = result.count
    print(f"✅ Scenario 5 (unpartitioned): {result.count} tables")

    # Test 10: Materialized views
    query_mvs = f"""
    SELECT COUNT(*) as count
    FROM `{PROJECT_ID}.INFORMATION_SCHEMA.TABLES`
    WHERE table_type = 'MATERIALIZED_VIEW'
    """
    result = list(client.query(query_mvs).result())[0]
    scenarios_detected['unused_materialized_views'] = result.count
    print(f"✅ Scenario 10 (materialized views): {result.count} views")

    # Rapport final
    print("\n📊 Detection Summary:")
    total_waste = sum(scenarios_detected.values())
    for scenario, count in scenarios_detected.items():
        if count > 0:
            print(f"  - {scenario}: {count} resources")

    print(f"\n✅ Total waste resources detected: {total_waste}")

if __name__ == '__main__':
    test_all_scenarios()
```

**Exécution :**
```bash
export PROJECT_ID="cloudwaste-test-XXXXXXXXXX"
python3 validate_bigquery_scenarios.py
```

---

### Cleanup

```bash
# Supprimer datasets test
bq rm -r -f -d ${PROJECT_ID}:test_waste_detection
bq rm -r -f -d ${PROJECT_ID}:test_empty_dataset
bq rm -r -f -d ${PROJECT_ID}:test_untagged_dataset

# Vérifier suppression
bq ls
```

---

## Références

### Documentation GCP

- [BigQuery API](https://cloud.google.com/bigquery/docs/reference/rest)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [INFORMATION_SCHEMA](https://cloud.google.com/bigquery/docs/information-schema-intro)
- [INFORMATION_SCHEMA.TABLES](https://cloud.google.com/bigquery/docs/information-schema-tables)
- [INFORMATION_SCHEMA.JOBS_BY_PROJECT](https://cloud.google.com/bigquery/docs/information-schema-jobs)
- [Partitioning Guide](https://cloud.google.com/bigquery/docs/partitioned-tables)
- [Clustering Guide](https://cloud.google.com/bigquery/docs/clustered-tables)
- [Materialized Views](https://cloud.google.com/bigquery/docs/materialized-views-intro)
- [Flat-Rate Pricing](https://cloud.google.com/bigquery/docs/reservations-intro)

### CloudWaste Documentation

- [GCP.md](./GCP.md) - Listing 27 ressources GCP
- [GCP_COMPUTE_ENGINE_SCENARIOS_100.md](./GCP_COMPUTE_ENGINE_SCENARIOS_100.md)
- [GCP_PERSISTENT_DISK_SCENARIOS_100.md](./GCP_PERSISTENT_DISK_SCENARIOS_100.md)
- [GCP_GKE_CLUSTER_SCENARIOS_100.md](./GCP_GKE_CLUSTER_SCENARIOS_100.md)
- [GCP_CLOUD_SQL_SCENARIOS_100.md](./GCP_CLOUD_SQL_SCENARIOS_100.md)
- [GCP_CLOUD_SPANNER_SCENARIOS_100.md](./GCP_CLOUD_SPANNER_SCENARIOS_100.md)
- [GCP_BIGTABLE_SCENARIOS_100.md](./GCP_BIGTABLE_SCENARIOS_100.md)

### Équivalences AWS/Azure

- **AWS Redshift** → GCP BigQuery (data warehouse)
- **Azure Synapse Analytics** → GCP BigQuery
- **Snowflake** → GCP BigQuery (competitor)
- **AWS Athena** → GCP BigQuery (serverless query)

### Best Practices

1. **Partitioning** : Tables >1 TB devraient toujours être partitionnées (date/timestamp/integer)
2. **Clustering** : Tables >100 GB avec filters communs devraient être clustered
3. **Column Selection** : Toujours SELECT colonnes spécifiques (jamais SELECT *)
4. **Materialized Views** : Pré-aggréger données fréquemment requêtées
5. **Flat-Rate** : Switch si query costs >$2,000/mois et workload stable
6. **Long-term Storage** : Transition automatique après 90j (-50% coût)
7. **Table Expiration** : Configurer expiration pour tables temporaires/staging
8. **Labels** : Taguer tous datasets pour cost allocation

---

**Dernière mise à jour :** 2 novembre 2025
**Status :** ✅ Spécification complète - Prêt pour implémentation
**Version :** 1.0
**Auteur :** CloudWaste Team
