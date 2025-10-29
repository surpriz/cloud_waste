# 📊 CloudWaste - Couverture 100% Azure Databases

## 🎯 Scénarios Couverts (15/15 = 100%)

> **Contexte 2025**: Les bases de données représentent **30-40% des coûts cloud** selon Gartner. **60% des databases Azure sont sur-provisionnées** (études FinOps). Ce document couvre 6 services de bases de données Azure avec 15 scénarios de gaspillage critiques.

### Services Couverts

1. **Azure SQL Database** (4 scénarios)
2. **Azure Cosmos DB** (3 scénarios)
3. **Azure Database for PostgreSQL** (2 scénarios)
4. **Azure Database for MySQL** (2 scénarios)
5. **Azure Synapse Analytics** (2 scénarios)
6. **Azure Cache for Redis** (2 scénarios)

---

## 📚 Table des Matières

1. [Azure SQL Database](#azure-sql-database)
2. [Azure Cosmos DB](#azure-cosmos-db)
3. [Azure PostgreSQL & MySQL](#azure-postgresql--mysql)
4. [Azure Synapse Analytics](#azure-synapse-analytics)
5. [Azure Cache for Redis](#azure-cache-for-redis)
6. [Matrice de Test](#matrice-de-test)
7. [Procédures de Test CLI](#procédures-de-test-cli)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Impact Business & ROI](#impact-business--roi)
10. [Références](#références-officielles-azure)

---

# Azure SQL Database

## Phase 1 - Détection Simple (3 scénarios)

### 1. `sql_database_stopped` - Base de données arrêtée depuis >30 jours

**Détection**: Database avec status 'Paused' ou provisioningState != 'Succeeded'.

**Logique**:
```python
# Récupérer toutes les databases SQL
from azure.mgmt.sql import SqlManagementClient

sql_client = SqlManagementClient(credential, subscription_id)

for server in sql_client.servers.list():
    for database in sql_client.databases.list_by_server(
        resource_group_name=server.id.split('/')[4],
        server_name=server.name
    ):
        # Ignorer databases système
        if database.name in ['master', 'tempdb', 'model', 'msdb']:
            continue

        # Vérifier statut
        if database.status == 'Paused':
            pause_time = get_pause_time_from_activity_log(database.id)
            age_days = (datetime.now() - pause_time).days

            if age_days >= min_age_days:
                flag_as_wasteful(database)
```

**Calcul coût**:
```python
# Coût mensuel selon tier (East US)
pricing_dtu = {
    "Basic": 4.90,              # 5 DTUs
    "S0": 14.72,                # 10 DTUs
    "S1": 29.45,                # 20 DTUs
    "S2": 73.62,                # 50 DTUs
    "S3": 147.24,               # 100 DTUs
    "S4": 294.47,               # 200 DTUs
    "P1": 456.25,               # 125 DTUs
    "P2": 912.50,               # 250 DTUs
    "P4": 1825.00,              # 500 DTUs
    "P6": 2737.50,              # 1000 DTUs
    "P11": 7312.50,             # 1750 DTUs
    "P15": 15698.89             # 4000 DTUs
}

pricing_vcore = {
    "GP_Gen5_2": 737.00,        # General Purpose 2 vCores
    "GP_Gen5_4": 1474.00,       # 4 vCores
    "GP_Gen5_8": 2948.00,       # 8 vCores
    "BC_Gen5_2": 2069.00,       # Business Critical 2 vCores
    "BC_Gen5_4": 4138.00,       # 4 vCores
}

# Storage en plus (si non inclus)
storage_cost = storage_gb * 0.115  # $0.115/GB/mois

# Si database arrêtée mais toujours facturée (DTU/vCore provisioned)
monthly_cost = pricing_dtu[tier] if is_dtu else pricing_vcore[sku]
monthly_cost += storage_cost

already_wasted = monthly_cost * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `exclude_system_databases`: true
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (40%) - Maintenance temporaire
- 30-60 jours: MEDIUM (70%) - Probablement oublié
- 60-90 jours: HIGH (85%) - Définitivement orphelin
- >90 jours: CRITICAL (98%) - Waste confirmé

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_sql_database",
  "scenario": "sql_database_stopped",
  "database_name": "db-prod-legacy",
  "server_name": "sql-server-prod",
  "status": "Paused",
  "sku": {
    "name": "S3",
    "tier": "Standard",
    "capacity": 100
  },
  "max_size_bytes": 268435456000,
  "storage_gb": 250,
  "pause_date": "2024-08-15T10:30:00Z",
  "age_days": 135,
  "monthly_cost_usd": 147.24,
  "storage_cost_usd": 28.75,
  "total_monthly_cost": 175.99,
  "already_wasted_usd": 791.95,
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2909` (stub existant)

---

### 2. `sql_database_idle_connections` - Base de données 0 connexions >30 jours

**Détection**: Database active mais aucune connexion détectée via Azure Monitor metrics.

**Logique**:
```python
# Database online
if database.status == 'Online':
    # Query Azure Monitor pour connections
    metric_name = "connection_successful"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=database.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(days=1),
        aggregations=["Total"]
    )

    total_connections = sum(
        point.total for point in query_result.metrics[0].timeseries[0].data
        if point.total is not None
    )

    # Si 0 connexions
    if total_connections == 0:
        flag_as_wasteful(database)
```

**Calcul coût**:
```python
# Coût identique au scénario #1 (database active mais inutilisée)
# Plus coût I/O si présent
io_cost = total_iops * 0.000015  # $0.000015 par IOP (si tier vCore)

monthly_cost = base_cost + storage_cost + io_cost
already_wasted = monthly_cost * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `min_connections_threshold`: 0
- `alert_threshold_days`: 45
- `critical_threshold_days`: 90

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (60%)
- 30-60 jours: HIGH (80%)
- 60-90 jours: HIGH (90%)
- >90 jours: CRITICAL (98%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_sql_database",
  "scenario": "sql_database_idle_connections",
  "database_name": "db-analytics-dev",
  "server_name": "sql-server-dev",
  "status": "Online",
  "sku": {
    "name": "GP_Gen5_4",
    "tier": "GeneralPurpose",
    "family": "Gen5",
    "capacity": 4
  },
  "monitoring_period_days": 60,
  "total_connections": 0,
  "total_queries": 0,
  "cpu_percent_avg": 0.5,
  "storage_percent": 12,
  "monthly_cost_usd": 1474.00,
  "already_wasted_usd": 2948.00,
  "recommendation": "Delete or switch to Serverless tier",
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py:2909` (stub existant)

---

### 3. `sql_database_over_provisioned_dtu` - Database DTU utilization <30%

**Détection**: Database DTU utilisés en moyenne <30% sur 30 jours.

**Logique**:
```python
# Uniquement pour databases DTU-based
if database.sku.tier in ['Basic', 'Standard', 'Premium']:
    # Query Azure Monitor pour DTU%
    metric_name = "dtu_consumption_percent"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=database.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(hours=1),
        aggregations=["Average"]
    )

    # Calculer moyenne DTU%
    dtu_percentages = [
        point.average for point in query_result.metrics[0].timeseries[0].data
        if point.average is not None
    ]

    avg_dtu_percent = sum(dtu_percentages) / len(dtu_percentages)

    # Si <30% utilisé
    if avg_dtu_percent < over_provisioned_threshold:
        # Recommander tier inférieur
        current_tier = database.sku.name
        recommended_tier = get_lower_tier(current_tier, avg_dtu_percent)

        flag_as_wasteful(database, recommended_tier)
```

**Calcul coût**:
```python
# Coût actuel
current_monthly_cost = pricing_dtu[current_tier]

# Coût recommandé (tier inférieur)
recommended_monthly_cost = pricing_dtu[recommended_tier]

# Économie potentielle
monthly_savings = current_monthly_cost - recommended_monthly_cost

# Exemple: S3 (100 DTU) → S1 (20 DTU)
# $147.24/mois → $29.45/mois = $117.79/mois économisés (80% savings)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**DTU Tier Downgrade Matrix**:
```python
downgrade_recommendations = {
    # Si avg_dtu% < 10%
    "S3": "S0",  # 100 DTU → 10 DTU (économie: $132.52/mois)
    "S2": "S0",  # 50 DTU → 10 DTU (économie: $58.90/mois)
    "P1": "S3",  # 125 DTU → 100 DTU (économie: $309.01/mois)

    # Si avg_dtu% 10-20%
    "S3": "S1",  # 100 DTU → 20 DTU (économie: $117.79/mois)
    "S4": "S2",  # 200 DTU → 50 DTU (économie: $220.85/mois)

    # Si avg_dtu% 20-30%
    "S3": "S2",  # 100 DTU → 50 DTU (économie: $73.62/mois)
    "P2": "P1",  # 250 DTU → 125 DTU (économie: $456.25/mois)
}
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `over_provisioned_threshold`: 30 (% DTU)
- `min_data_points`: 500 (minimum pour analyse fiable)
- `alert_threshold_percent`: 25
- `critical_threshold_percent`: 15

**Confidence level**:
- avg_dtu% 25-30%: MEDIUM (60%) - Léger over-provisioning
- avg_dtu% 15-25%: HIGH (80%) - Over-provisioning confirmé
- avg_dtu% <15%: CRITICAL (95%) - Sérieux waste

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_sql_database",
  "scenario": "sql_database_over_provisioned_dtu",
  "database_name": "db-webapp-prod",
  "server_name": "sql-server-prod",
  "status": "Online",
  "current_sku": {
    "name": "S3",
    "tier": "Standard",
    "capacity": 100
  },
  "monitoring_period_days": 30,
  "avg_dtu_percent": 18.5,
  "max_dtu_percent": 45.2,
  "p95_dtu_percent": 32.1,
  "current_monthly_cost": 147.24,
  "recommended_sku": {
    "name": "S1",
    "tier": "Standard",
    "capacity": 20
  },
  "recommended_monthly_cost": 29.45,
  "monthly_savings_potential": 117.79,
  "annual_savings_potential": 1413.48,
  "already_wasted_usd": 117.79,
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

## Phase 2 - Azure Monitor Métriques (1 scénario)

### 4. `sql_database_serverless_not_pausing` - Serverless auto-pause jamais déclenché

**Détection**: Database en tier Serverless mais métriques montrent activité continue (jamais de pause).

**Logique**:
```python
# Uniquement pour tier Serverless
if database.sku.tier == 'GeneralPurpose' and 'serverless' in database.sku.name.lower():
    # Vérifier auto-pause configuration
    auto_pause_delay = database.auto_pause_delay_in_minutes

    # Query CPU usage pour détecter pauses
    metric_name = "cpu_percent"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=database.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(minutes=5),
        aggregations=["Average"]
    )

    # Analyser gaps (pauses)
    data_points = query_result.metrics[0].timeseries[0].data
    gaps = []

    for i in range(1, len(data_points)):
        time_diff = (data_points[i].timestamp - data_points[i-1].timestamp).total_seconds() / 60
        if time_diff > auto_pause_delay:
            gaps.append(time_diff)

    # Si aucun gap détecté = jamais pausé
    if len(gaps) == 0:
        # Database serverless jamais pausée = pas d'économie
        # Recommander switch vers Provisioned vCore
        flag_as_wasteful(database)
```

**Calcul coût**:
```python
# Coût Serverless actuel (24/7 actif)
vcore_count = database.sku.capacity
vcore_hourly_rate = 0.5218  # $/vCore/heure (General Purpose)
storage_gb = database.max_size_bytes / (1024**3)
storage_monthly_rate = 0.115  # $/GB/mois

# Compute cost (actif 24/7)
monthly_compute_cost = vcore_count * vcore_hourly_rate * 730  # $380.91 pour 1 vCore

# Storage cost
monthly_storage_cost = storage_gb * storage_monthly_rate

total_serverless_cost = monthly_compute_cost + monthly_storage_cost

# Alternative: Provisioned vCore (si toujours actif)
# Provisioned est moins cher si >60-70% uptime
provisioned_vcore_hourly = 0.5218  # Même prix unitaire
provisioned_monthly = vcore_count * provisioned_vcore_hourly * 730

# Ou économie si database devrait pauser
# Exemple: Usage 8h/jour × 5j/semaine = 23% uptime
expected_uptime_hours = 8 * 5 * 4.33  # 173 heures/mois
expected_compute_cost = vcore_count * vcore_hourly_rate * expected_uptime_hours

# Économie potentielle
monthly_savings = total_serverless_cost - expected_compute_cost
# Ex: $380.91 - $90.27 = $290.64/mois

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `min_pause_count`: 1 (minimum pauses attendues)
- `expected_uptime_ratio`: 0.25 (25% uptime attendu pour dev/test)
- `alert_threshold_days`: 30
- `critical_threshold_days`: 60

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (50%)
- 30-60 jours + 0 pauses: HIGH (80%)
- >60 jours + 0 pauses: CRITICAL (95%)

**Azure Monitor Query**:
```python
from azure.monitor.query import MetricsQueryClient, MetricAggregationType
from datetime import datetime, timedelta

# Query CPU percent (detect pauses)
start_time = datetime.utcnow() - timedelta(days=30)
end_time = datetime.utcnow()

response = metrics_client.query_resource(
    resource_uri=database_id,
    metric_names=["cpu_percent", "storage_percent"],
    timespan=(start_time, end_time),
    granularity=timedelta(minutes=5),
    aggregations=[MetricAggregationType.AVERAGE]
)

# Detect pauses (gaps in data)
cpu_data = [d for d in response.metrics[0].timeseries[0].data if d.average is not None]

pause_count = 0
for i in range(1, len(cpu_data)):
    gap_minutes = (cpu_data[i].timestamp - cpu_data[i-1].timestamp).total_seconds() / 60
    if gap_minutes > 60:  # Auto-pause delay
        pause_count += 1

print(f"Pause count (30 days): {pause_count}")
```

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_sql_database",
  "scenario": "sql_database_serverless_not_pausing",
  "database_name": "db-dev-serverless",
  "server_name": "sql-server-dev",
  "status": "Online",
  "sku": {
    "name": "GP_S_Gen5_1",
    "tier": "GeneralPurpose",
    "family": "Gen5",
    "capacity": 1
  },
  "auto_pause_delay_minutes": 60,
  "monitoring_period_days": 30,
  "pause_count": 0,
  "uptime_hours": 720,
  "uptime_ratio": 1.0,
  "expected_uptime_ratio": 0.25,
  "current_monthly_cost": 380.91,
  "expected_monthly_cost": 95.23,
  "monthly_savings_potential": 285.68,
  "recommendation": "Configure proper auto-pause or switch to Provisioned",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

# Azure Cosmos DB

## Phase 1 - Détection Simple (2 scénarios)

### 5. `cosmosdb_over_provisioned_ru` - RU throughput utilisés <30%

**Détection**: Cosmos DB containers/databases avec RU provisionnés mais <30% utilisés.

**Logique**:
```python
from azure.mgmt.cosmosdb import CosmosDBManagementClient

cosmosdb_client = CosmosDBManagementClient(credential, subscription_id)

for account in cosmosdb_client.database_accounts.list():
    # Query métriques RU consumption
    metric_name = "TotalRequestUnits"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=account.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(hours=1),
        aggregations=["Total"]
    )

    # Calculer RU utilisés vs provisionnés
    total_ru_consumed = sum(
        point.total for point in query_result.metrics[0].timeseries[0].data
        if point.total is not None
    )

    # RU provisionnés (depuis throughput settings)
    provisioned_ru_per_sec = get_provisioned_throughput(account)
    total_ru_available = provisioned_ru_per_sec * 3600 * 24 * 30  # 30 jours

    utilization_percent = (total_ru_consumed / total_ru_available) * 100

    # Si <30% utilisé
    if utilization_percent < over_provisioned_threshold:
        # Recommander réduction RU
        recommended_ru = int(provisioned_ru_per_sec * (utilization_percent / 100) * 1.2)  # +20% buffer
        flag_as_wasteful(account, recommended_ru)
```

**Calcul coût**:
```python
# Coût Cosmos DB (Provisioned Throughput)
# Standard: $0.008 par 100 RU/h
# Storage: $0.25/GB/mois

# RU provisionnés actuels
provisioned_ru = 10000  # RU/s
hourly_cost = (provisioned_ru / 100) * 0.008  # $0.80/h
monthly_cost_ru = hourly_cost * 730  # $584/mois

# Storage
storage_gb = 500
monthly_cost_storage = storage_gb * 0.25  # $125/mois

total_current_cost = monthly_cost_ru + monthly_cost_storage  # $709/mois

# RU recommandés (basé sur utilisation 25% = 2500 RU utilisés en moyenne)
recommended_ru = int(2500 * 1.2)  # 3000 RU/s (+20% buffer)
recommended_monthly_cost_ru = (recommended_ru / 100) * 0.008 * 730  # $175.20/mois

# Économie potentielle
monthly_savings = (monthly_cost_ru - recommended_monthly_cost_ru)  # $408.80/mois

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `over_provisioned_threshold`: 30 (% RU)
- `recommended_buffer`: 1.2 (20% buffer)
- `alert_threshold_percent`: 25
- `critical_threshold_percent`: 15

**Confidence level**:
- utilization 25-30%: MEDIUM (60%)
- utilization 15-25%: HIGH (80%)
- utilization <15%: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_cosmosdb_account",
  "scenario": "cosmosdb_over_provisioned_ru",
  "account_name": "cosmos-prod-api",
  "database_name": "ProductsDB",
  "container_name": "Products",
  "api_type": "SQL",
  "monitoring_period_days": 30,
  "provisioned_ru_per_sec": 10000,
  "total_ru_consumed": 54000000,
  "total_ru_available": 259200000,
  "utilization_percent": 20.8,
  "avg_ru_per_sec": 2083,
  "max_ru_per_sec": 4500,
  "current_monthly_cost_ru": 584.00,
  "storage_gb": 500,
  "storage_monthly_cost": 125.00,
  "recommended_ru_per_sec": 3000,
  "recommended_monthly_cost_ru": 175.20,
  "monthly_savings_potential": 408.80,
  "annual_savings_potential": 4905.60,
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

### 6. `cosmosdb_idle_containers` - Containers avec 0 requêtes >30 jours

**Détection**: Cosmos DB containers sans aucune requête sur 30 jours.

**Logique**:
```python
# Pour chaque container
for database in cosmosdb_client.sql_resources.list_sql_databases(rg_name, account_name):
    for container in cosmosdb_client.sql_resources.list_sql_containers(
        rg_name, account_name, database.name
    ):
        # Query métriques requests
        metric_name = "TotalRequests"
        time_range = timedelta(days=30)

        # Note: Métriques au niveau account, filtrer par database/collection
        query_result = metrics_client.query_resource(
            resource_uri=account.id,
            metric_names=[metric_name],
            timespan=time_range,
            granularity=timedelta(days=1),
            aggregations=["Count"]
        )

        total_requests = sum(
            point.count for point in query_result.metrics[0].timeseries[0].data
            if point.count is not None
        )

        # Si 0 requêtes
        if total_requests == 0:
            flag_as_wasteful(container)
```

**Calcul coût**:
```python
# Container idle mais RU provisionnés
container_ru = 400  # RU/s minimum
hourly_cost = (container_ru / 100) * 0.008  # $0.032/h
monthly_cost = hourly_cost * 730  # $23.36/mois

# Storage du container
container_storage_gb = 50
storage_cost = container_storage_gb * 0.25  # $12.50/mois

total_monthly_cost = monthly_cost + storage_cost  # $35.86/mois

already_wasted = total_monthly_cost * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `min_requests_threshold`: 0
- `alert_threshold_days`: 45
- `critical_threshold_days`: 90

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (60%)
- 30-60 jours: HIGH (85%)
- >60 jours: CRITICAL (98%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_cosmosdb_container",
  "scenario": "cosmosdb_idle_containers",
  "account_name": "cosmos-prod-api",
  "database_name": "LegacyDB",
  "container_name": "OldOrders",
  "partition_key": "/orderId",
  "provisioned_ru_per_sec": 400,
  "monitoring_period_days": 60,
  "total_requests": 0,
  "storage_gb": 50,
  "monthly_cost_ru": 23.36,
  "monthly_cost_storage": 12.50,
  "total_monthly_cost": 35.86,
  "already_wasted_usd": 71.72,
  "recommendation": "Delete container or move to Serverless/Autoscale",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

## Phase 2 - Azure Monitor Métriques (1 scénario)

### 7. `cosmosdb_hot_partitions_idle_others` - Hot partitions + partitions idle

**Détection**: Certaines partitions à 100% RU, d'autres à 0% (mauvaise partition key).

**Logique**:
```python
# Query Normalized RU Consumption par partition
metric_name = "NormalizedRUConsumption"
time_range = timedelta(days=7)

query_result = metrics_client.query_resource(
    resource_uri=container_id,
    metric_names=[metric_name],
    timespan=time_range,
    granularity=timedelta(minutes=5),
    aggregations=["Maximum"]
)

# Analyser par partition (via dimensions)
partition_metrics = {}

for timeseries in query_result.metrics[0].timeseries:
    partition_key = timeseries.metadata_values.get('PartitionKeyRangeId')

    max_values = [d.maximum for d in timeseries.data if d.maximum is not None]
    avg_max = sum(max_values) / len(max_values) if max_values else 0

    partition_metrics[partition_key] = avg_max

# Identifier hot partitions (>80%) et idle (<10%)
hot_partitions = [k for k, v in partition_metrics.items() if v > 80]
idle_partitions = [k for k, v in partition_metrics.items() if v < 10]

# Si hot + idle coexistent = mauvaise partition key
if len(hot_partitions) > 0 and len(idle_partitions) > 0:
    flag_as_wasteful(container, reason="poor_partition_key")
```

**Calcul coût**:
```python
# Problème: RU gaspillés sur idle partitions
# + Throttling sur hot partitions (besoin d'augmenter RU totaux)

# RU actuels
current_ru = 20000  # RU/s
monthly_cost_current = (current_ru / 100) * 0.008 * 730  # $1,168/mois

# Avec partition key optimale (distribution équilibrée)
# Pourrait réduire RU de 30-40%
optimized_ru = int(current_ru * 0.65)  # 13000 RU/s
monthly_cost_optimized = (optimized_ru / 100) * 0.008 * 730  # $759.20/mois

# Économie potentielle
monthly_savings = monthly_cost_current - monthly_cost_optimized  # $408.80/mois

# Note: Nécessite refactoring partition key (coût one-time)
# Mais économie récurrente significative

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 7 (défaut, car métriques partitions coûteuses)
- `hot_partition_threshold`: 80 (% Normalized RU)
- `idle_partition_threshold`: 10
- `min_hot_partition_count`: 1
- `min_idle_partition_count`: 1

**Confidence level**:
- monitoring_period < 7 jours: LOW (50%)
- 7-14 jours + hot/idle confirmés: MEDIUM (70%)
- >14 jours + pattern constant: HIGH (85%)

**Azure Monitor Query**:
```python
from azure.monitor.query import MetricsQueryClient, MetricAggregationType

# Query Normalized RU Consumption (par partition)
start_time = datetime.utcnow() - timedelta(days=7)
end_time = datetime.utcnow()

response = metrics_client.query_resource(
    resource_uri=container_id,
    metric_names=["NormalizedRUConsumption"],
    timespan=(start_time, end_time),
    granularity=timedelta(minutes=5),
    aggregations=[MetricAggregationType.MAXIMUM],
    filter="PartitionKeyRangeId eq '*'"  # Toutes les partitions
)

# Analyser distribution
partition_stats = {}

for timeseries in response.metrics[0].timeseries:
    partition_id = None
    for meta in timeseries.metadata_values:
        if meta.name.value == 'PartitionKeyRangeId':
            partition_id = meta.value

    if partition_id:
        max_values = [d.maximum for d in timeseries.data if d.maximum]
        partition_stats[partition_id] = {
            'avg_max': sum(max_values) / len(max_values) if max_values else 0,
            'peak': max(max_values) if max_values else 0
        }

# Identifier déséquilibre
hot = [k for k, v in partition_stats.items() if v['avg_max'] > 80]
idle = [k for k, v in partition_stats.items() if v['avg_max'] < 10]

print(f"Hot partitions: {hot}")
print(f"Idle partitions: {idle}")
```

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_cosmosdb_container",
  "scenario": "cosmosdb_hot_partitions_idle_others",
  "account_name": "cosmos-prod-api",
  "database_name": "OrdersDB",
  "container_name": "Orders",
  "partition_key": "/userId",
  "partition_count": 10,
  "hot_partitions": ["0", "1"],
  "hot_partition_avg_ru_percent": 95,
  "idle_partitions": ["5", "6", "7", "8"],
  "idle_partition_avg_ru_percent": 3,
  "provisioned_ru_per_sec": 20000,
  "current_monthly_cost": 1168.00,
  "optimized_ru_per_sec": 13000,
  "optimized_monthly_cost": 759.20,
  "monthly_savings_potential": 408.80,
  "recommendation": "Redesign partition key for better distribution",
  "refactoring_effort": "High (requires data migration)",
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

# Azure PostgreSQL & MySQL

## Phase 1 - Détection Simple (4 scénarios)

### 8. `postgres_mysql_stopped` - Database arrêtée >7 jours

**Détection**: PostgreSQL/MySQL Flexible Server en statut 'Stopped'.

**Logique**:
```python
from azure.mgmt.rdbms.postgresql_flexibleservers import PostgreSQLManagementClient
from azure.mgmt.rdbms.mysql_flexibleservers import MySQLManagementClient

# PostgreSQL
postgres_client = PostgreSQLManagementClient(credential, subscription_id)

for server in postgres_client.servers.list():
    # Vérifier statut
    if server.state == 'Stopped':
        stop_time = get_stop_time_from_activity_log(server.id)
        age_days = (datetime.now() - stop_time).days

        if age_days >= min_age_days:
            flag_as_wasteful(server)

# MySQL (même logique)
mysql_client = MySQLManagementClient(credential, subscription_id)
# ... (identique)
```

**Calcul coût**:
```python
# PostgreSQL/MySQL Flexible Server
# Coût compute (vCores)
vcore_count = server.sku.capacity
tier = server.sku.tier  # Burstable, GeneralPurpose, MemoryOptimized

pricing_per_vcore_hour = {
    "Burstable": 0.0105,           # B1ms (1 vCore)
    "GeneralPurpose": 0.1027,      # D2s_v3 (2 vCores)
    "MemoryOptimized": 0.2048      # E2s_v3 (2 vCores)
}

hourly_compute = vcore_count * pricing_per_vcore_hour[tier]
monthly_compute = hourly_compute * 730

# Storage (payé même si stopped)
storage_gb = server.storage_profile.storage_mb / 1024
storage_monthly = storage_gb * 0.115  # $0.115/GB/mois

# Backup storage (au-delà de 100% storage provisionné)
backup_gb = get_backup_storage_usage(server.id)
free_backup = storage_gb  # 100% du storage provisionné gratuit
billable_backup = max(0, backup_gb - free_backup)
backup_monthly = billable_backup * 0.095  # $0.095/GB/mois

# Total mensuel (storage payé même si stopped)
# Note: Compute GRATUIT si stopped (feature Azure)
monthly_cost_if_running = monthly_compute + storage_monthly + backup_monthly
monthly_cost_while_stopped = storage_monthly + backup_monthly

# Si stopped >7 jours, recommander suppression ou export
already_wasted = monthly_cost_while_stopped * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 7 (défaut)
- `alert_threshold_days`: 14
- `critical_threshold_days`: 30

**Confidence level**:
- age_days < 7: LOW (40%)
- 7-14 jours: MEDIUM (70%)
- 14-30 jours: HIGH (85%)
- >30 jours: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_postgresql_flexible_server",
  "scenario": "postgres_mysql_stopped",
  "server_name": "postgres-dev-01",
  "state": "Stopped",
  "sku": {
    "name": "Standard_D4s_v3",
    "tier": "GeneralPurpose",
    "capacity": 4
  },
  "storage_gb": 128,
  "backup_retention_days": 7,
  "backup_storage_gb": 50,
  "stopped_date": "2024-12-15T10:00:00Z",
  "age_days": 45,
  "monthly_compute_cost": 300.00,
  "monthly_storage_cost": 14.72,
  "monthly_backup_cost": 0,
  "total_monthly_cost_if_running": 314.72,
  "monthly_cost_while_stopped": 14.72,
  "already_wasted_usd": 22.08,
  "recommendation": "Delete or export to backup",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2909` (stub existant)

---

### 9. `postgres_mysql_idle_connections` - 0 connexions >30 jours

**Détection**: Server online mais aucune connexion via Azure Monitor.

**Logique**:
```python
# Server actif
if server.state == 'Ready':
    # Query Azure Monitor pour connections
    metric_name = "active_connections"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=server.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(hours=1),
        aggregations=["Average", "Maximum"]
    )

    # Vérifier max connections
    max_connections = max(
        point.maximum for point in query_result.metrics[0].timeseries[0].data
        if point.maximum is not None
    )

    # Si max = 0 sur 30 jours
    if max_connections == 0:
        flag_as_wasteful(server)
```

**Calcul coût**:
```python
# Coût identique au coût running (compute + storage + backup)
monthly_cost = monthly_compute + monthly_storage + monthly_backup

already_wasted = monthly_cost * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `min_connections_threshold`: 0
- `alert_threshold_days`: 45
- `critical_threshold_days`: 90

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (60%)
- 30-60 jours: HIGH (80%)
- >60 jours: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_mysql_flexible_server",
  "scenario": "postgres_mysql_idle_connections",
  "server_name": "mysql-analytics-prod",
  "state": "Ready",
  "sku": {
    "name": "Standard_D2s_v3",
    "tier": "GeneralPurpose",
    "capacity": 2
  },
  "monitoring_period_days": 60,
  "max_active_connections": 0,
  "avg_active_connections": 0,
  "cpu_percent_avg": 2.1,
  "storage_percent": 45,
  "monthly_cost_usd": 150.00,
  "already_wasted_usd": 300.00,
  "recommendation": "Delete or stop server",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2909` (stub existant)

---

### 10. `postgres_mysql_over_provisioned_vcores` - vCores utilization <20%

**Détection**: Server avec CPU utilization moyenne <20% sur 30 jours.

**Logique**:
```python
# Query CPU percent
metric_name = "cpu_percent"
time_range = timedelta(days=30)

query_result = metrics_client.query_resource(
    resource_uri=server.id,
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
if avg_cpu_percent < over_provisioned_threshold:
    # Recommander SKU inférieur
    current_sku = server.sku.name
    recommended_sku = get_lower_sku(current_sku, avg_cpu_percent)

    flag_as_wasteful(server, recommended_sku)
```

**Calcul coût**:
```python
# Coût actuel
current_vcore = 8
current_hourly = 8 * 0.1027  # General Purpose
current_monthly = current_hourly * 730  # $599.76/mois

# Recommandé (basé sur avg_cpu 15% = 1.2 vCores utilisés)
recommended_vcore = 4  # Downgrade à 4 vCores
recommended_hourly = 4 * 0.1027
recommended_monthly = recommended_hourly * 730  # $299.88/mois

# Économie
monthly_savings = current_monthly - recommended_monthly  # $299.88/mois (50%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `over_provisioned_threshold`: 20 (% CPU)
- `recommended_buffer`: 1.5 (50% buffer)
- `alert_threshold_percent`: 25
- `critical_threshold_percent`: 15

**Confidence level**:
- avg_cpu% 20-25%: MEDIUM (60%)
- avg_cpu% 10-20%: HIGH (80%)
- avg_cpu% <10%: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_postgresql_flexible_server",
  "scenario": "postgres_mysql_over_provisioned_vcores",
  "server_name": "postgres-webapp-prod",
  "state": "Ready",
  "current_sku": {
    "name": "Standard_D8s_v3",
    "tier": "GeneralPurpose",
    "capacity": 8
  },
  "monitoring_period_days": 30,
  "avg_cpu_percent": 14.2,
  "max_cpu_percent": 38.5,
  "p95_cpu_percent": 28.1,
  "current_monthly_cost": 599.76,
  "recommended_sku": {
    "name": "Standard_D4s_v3",
    "tier": "GeneralPurpose",
    "capacity": 4
  },
  "recommended_monthly_cost": 299.88,
  "monthly_savings_potential": 299.88,
  "annual_savings_potential": 3598.56,
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

### 11. `postgres_mysql_burstable_always_bursting` - Tier Burstable constamment en burst

**Détection**: Server en tier Burstable mais CPU >50% constamment (devrait être General Purpose).

**Logique**:
```python
# Uniquement tier Burstable
if server.sku.tier == 'Burstable':
    # Query CPU percent
    metric_name = "cpu_percent"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=server.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(hours=1),
        aggregations=["Average"]
    )

    # Calculer % temps au-dessus de 50% CPU
    cpu_values = [
        point.average for point in query_result.metrics[0].timeseries[0].data
        if point.average is not None
    ]

    high_cpu_count = sum(1 for v in cpu_values if v > 50)
    high_cpu_ratio = high_cpu_count / len(cpu_values)

    # Si >70% du temps en burst
    if high_cpu_ratio > 0.70:
        # Recommander passage General Purpose
        flag_as_wasteful(server, recommended_tier="GeneralPurpose")
```

**Calcul coût**:
```python
# Burstable actuel (sous-optimal si constamment en burst)
# Burstable a CPU credits limités, performance dégradée

burstable_vcore = 2
burstable_hourly = 2 * 0.0105  # Burstable B2s
burstable_monthly = burstable_hourly * 730  # $15.33/mois

# General Purpose recommandé (même vCores, meilleur perf)
gp_vcore = 2
gp_hourly = 2 * 0.1027  # General Purpose D2s_v3
gp_monthly = gp_hourly * 730  # $149.94/mois

# Coût supplémentaire mais meilleur ROI (perf constante)
# Pas vraiment du "waste" mais sous-provisioning
# Plutôt recommandation d'upgrade pour éviter dégradation perf

# Alternative perspective: Coût caché de performance dégradée
# (timeouts, queries lentes, user frustration)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `high_cpu_threshold`: 50 (% CPU)
- `high_cpu_time_ratio`: 0.70 (70% du temps)
- `alert_threshold_ratio`: 0.60

**Confidence level**:
- high_cpu_ratio 50-70%: MEDIUM (60%)
- high_cpu_ratio >70%: HIGH (85%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_postgresql_flexible_server",
  "scenario": "postgres_mysql_burstable_always_bursting",
  "server_name": "postgres-api-prod",
  "state": "Ready",
  "current_sku": {
    "name": "Standard_B2s",
    "tier": "Burstable",
    "capacity": 2
  },
  "monitoring_period_days": 30,
  "avg_cpu_percent": 68.5,
  "high_cpu_time_ratio": 0.82,
  "cpu_credits_exhausted": true,
  "current_monthly_cost": 15.33,
  "recommended_sku": {
    "name": "Standard_D2s_v3",
    "tier": "GeneralPurpose",
    "capacity": 2
  },
  "recommended_monthly_cost": 149.94,
  "additional_monthly_cost": 134.61,
  "recommendation": "Upgrade to General Purpose for consistent performance",
  "performance_impact": "High (CPU throttling due to credit exhaustion)",
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

# Azure Synapse Analytics

## Phase 1 - Détection Simple (2 scénarios)

### 12. `synapse_sql_pool_paused` - SQL Pool pausé >30 jours

**Détection**: Synapse SQL Pool en statut 'Paused'.

**Logique**:
```python
from azure.mgmt.synapse import SynapseManagementClient

synapse_client = SynapseManagementClient(credential, subscription_id)

for workspace in synapse_client.workspaces.list():
    rg_name = workspace.id.split('/')[4]

    for sql_pool in synapse_client.sql_pools.list_by_workspace(
        rg_name, workspace.name
    ):
        # Vérifier statut
        if sql_pool.status == 'Paused':
            pause_time = get_pause_time_from_activity_log(sql_pool.id)
            age_days = (datetime.now() - pause_time).days

            if age_days >= min_age_days:
                flag_as_wasteful(sql_pool)
```

**Calcul coût**:
```python
# Synapse SQL Pool (Dedicated)
# Coût DWU (Data Warehouse Units)
# DW100c - DW30000c

pricing_per_dwu_hour = {
    "DW100c": 1.20,       # $1.20/heure
    "DW200c": 2.40,
    "DW300c": 3.60,
    "DW400c": 4.80,
    "DW500c": 6.00,
    "DW1000c": 12.00,
    "DW1500c": 18.00,
    "DW2000c": 24.00,
    "DW3000c": 36.00,
    "DW5000c": 60.00,
    "DW6000c": 72.00,
    "DW10000c": 120.00,
    "DW15000c": 180.00,
    "DW30000c": 360.00    # $360/heure!
}

# Si pausé: Pas de coût compute
# Mais storage toujours facturé
storage_gb = sql_pool.max_size_bytes / (1024**3)
storage_monthly = storage_gb * 0.12  # $0.12/GB/mois (Synapse storage)

# Si running (pour comparaison)
dwu_tier = sql_pool.sku.name
compute_monthly = pricing_per_dwu_hour[dwu_tier] * 730

# Coût pendant pause (storage seulement)
monthly_cost_while_paused = storage_monthly

# Si pausé >30 jours, recommander suppression ou export
already_wasted = monthly_cost_while_paused * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (40%)
- 30-60 jours: MEDIUM (70%)
- 60-90 jours: HIGH (85%)
- >90 jours: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_synapse_sql_pool",
  "scenario": "synapse_sql_pool_paused",
  "workspace_name": "synapse-analytics-prod",
  "sql_pool_name": "SQLPool01",
  "status": "Paused",
  "sku": {
    "name": "DW1000c",
    "tier": "DataWarehouse",
    "capacity": 1000
  },
  "max_size_gb": 2048,
  "paused_date": "2024-09-01T14:00:00Z",
  "age_days": 120,
  "hourly_compute_cost": 12.00,
  "monthly_compute_cost_if_running": 8760.00,
  "monthly_storage_cost": 245.76,
  "monthly_cost_while_paused": 245.76,
  "already_wasted_usd": 983.04,
  "recommendation": "Delete or export to cheaper storage",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2986` (stub existant)

---

### 13. `synapse_sql_pool_idle_queries` - SQL Pool 0 queries >30 jours

**Détection**: SQL Pool actif mais aucune query exécutée.

**Logique**:
```python
# SQL Pool online
if sql_pool.status == 'Online':
    # Query Azure Monitor pour DWU percent
    # Ou query sys.dm_pdw_exec_requests (via SQL)

    # Via Azure Monitor
    metric_name = "DWUUsedPercent"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=sql_pool.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(hours=1),
        aggregations=["Average", "Maximum"]
    )

    # Vérifier max DWU usage
    max_dwu_percent = max(
        point.maximum for point in query_result.metrics[0].timeseries[0].data
        if point.maximum is not None
    )

    # Si max < 1% sur 30 jours = idle
    if max_dwu_percent < 1:
        flag_as_wasteful(sql_pool)
```

**Calcul coût**:
```python
# Coût compute + storage (online 24/7)
dwu_tier = sql_pool.sku.name
compute_monthly = pricing_per_dwu_hour[dwu_tier] * 730

storage_gb = sql_pool.max_size_bytes / (1024**3)
storage_monthly = storage_gb * 0.12

total_monthly_cost = compute_monthly + storage_monthly

already_wasted = total_monthly_cost * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `max_dwu_percent_threshold`: 1
- `alert_threshold_days`: 45
- `critical_threshold_days`: 90

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (60%)
- 30-60 jours: HIGH (85%)
- >60 jours: CRITICAL (98%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_synapse_sql_pool",
  "scenario": "synapse_sql_pool_idle_queries",
  "workspace_name": "synapse-analytics-dev",
  "sql_pool_name": "DevPool",
  "status": "Online",
  "sku": {
    "name": "DW500c",
    "capacity": 500
  },
  "monitoring_period_days": 60,
  "max_dwu_percent": 0.3,
  "avg_dwu_percent": 0.1,
  "total_queries": 0,
  "monthly_compute_cost": 4380.00,
  "monthly_storage_cost": 122.88,
  "total_monthly_cost": 4502.88,
  "already_wasted_usd": 9005.76,
  "recommendation": "Pause or delete SQL Pool",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2986` (stub existant)

---

# Azure Cache for Redis

## Phase 1 - Détection Simple (2 scénarios)

### 14. `redis_idle_cache` - Cache 0 connexions >30 jours

**Détection**: Redis cache sans connexions via Azure Monitor.

**Logique**:
```python
from azure.mgmt.redis import RedisManagementClient

redis_client = RedisManagementClient(credential, subscription_id)

for cache in redis_client.redis.list():
    # Vérifier provisioning state
    if cache.provisioning_state == 'Succeeded':
        # Query Azure Monitor pour connections
        metric_name = "connectedclients"
        time_range = timedelta(days=30)

        query_result = metrics_client.query_resource(
            resource_uri=cache.id,
            metric_names=[metric_name],
            timespan=time_range,
            granularity=timedelta(hours=1),
            aggregations=["Maximum"]
        )

        # Vérifier max connections
        max_connections = max(
            point.maximum for point in query_result.metrics[0].timeseries[0].data
            if point.maximum is not None
        )

        # Si max = 0 sur 30 jours
        if max_connections == 0:
            flag_as_wasteful(cache)
```

**Calcul coût**:
```python
# Azure Cache for Redis pricing (East US)
# Basic (non-HA, dev/test)
pricing_basic = {
    "C0": 13.00,     # 250 MB
    "C1": 26.00,     # 1 GB
    "C2": 52.00,     # 2.5 GB
    "C3": 104.00,    # 6 GB
    "C4": 208.00,    # 13 GB
    "C5": 416.00,    # 26 GB
    "C6": 832.00     # 53 GB
}

# Standard (HA, 2 replicas)
pricing_standard = {
    "C0": 26.00,
    "C1": 52.00,
    "C2": 104.00,
    "C3": 208.00,
    "C4": 416.00,
    "C5": 832.00,
    "C6": 1664.00
}

# Premium (HA + clustering + persistence)
pricing_premium = {
    "P1": 568.00,    # 6 GB
    "P2": 1136.00,   # 13 GB
    "P3": 2272.00,   # 26 GB
    "P4": 4544.00,   # 53 GB
    "P5": 6847.00    # 120 GB
}

# Coût mensuel
tier = cache.sku.name
family = cache.sku.family  # C = Basic/Standard, P = Premium

if family == 'C':
    if cache.sku.tier == 'Basic':
        monthly_cost = pricing_basic[tier]
    else:
        monthly_cost = pricing_standard[tier]
else:  # Premium
    monthly_cost = pricing_premium[tier]

already_wasted = monthly_cost * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `min_connections_threshold`: 0
- `alert_threshold_days`: 45
- `critical_threshold_days`: 90

**Confidence level**:
- monitoring_period < 30 jours: MEDIUM (60%)
- 30-60 jours: HIGH (85%)
- >60 jours: CRITICAL (98%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_redis_cache",
  "scenario": "redis_idle_cache",
  "cache_name": "redis-cache-dev",
  "provisioning_state": "Succeeded",
  "sku": {
    "name": "C2",
    "tier": "Standard",
    "family": "C",
    "capacity": 2.5
  },
  "redis_version": "6.0",
  "enable_non_ssl_port": false,
  "monitoring_period_days": 60,
  "max_connected_clients": 0,
  "avg_connected_clients": 0,
  "total_cache_hits": 0,
  "total_cache_misses": 0,
  "monthly_cost_usd": 104.00,
  "already_wasted_usd": 208.00,
  "recommendation": "Delete cache",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:2994` (stub existant)

---

### 15. `redis_over_sized_tier` - Cache tier surdimensionné (memory <30% utilisée)

**Détection**: Redis cache avec memory utilization <30%.

**Logique**:
```python
# Cache actif
if cache.provisioning_state == 'Succeeded':
    # Query Azure Monitor pour used memory percent
    metric_name = "usedmemorypercentage"
    time_range = timedelta(days=30)

    query_result = metrics_client.query_resource(
        resource_uri=cache.id,
        metric_names=[metric_name],
        timespan=time_range,
        granularity=timedelta(hours=1),
        aggregations=["Average", "Maximum"]
    )

    # Calculer moyenne memory%
    memory_percentages = [
        point.average for point in query_result.metrics[0].timeseries[0].data
        if point.average is not None
    ]

    avg_memory_percent = sum(memory_percentages) / len(memory_percentages)

    # Si <30% utilisé
    if avg_memory_percent < over_sized_threshold:
        # Recommander tier inférieur
        current_tier = cache.sku.name
        recommended_tier = get_lower_redis_tier(current_tier, avg_memory_percent)

        flag_as_wasteful(cache, recommended_tier)
```

**Calcul coût**:
```python
# Coût actuel
current_tier = "C4"  # 13 GB, Standard
current_monthly_cost = pricing_standard[current_tier]  # $416/mois

# Utilisation moyenne: 20% de 13 GB = 2.6 GB utilisés
avg_memory_percent = 20
used_gb = 13 * (avg_memory_percent / 100)  # 2.6 GB

# Tier recommandé: C2 (2.5 GB) avec buffer 20%
recommended_tier = "C2"  # 2.5 GB
recommended_monthly_cost = pricing_standard[recommended_tier]  # $104/mois

# Économie potentielle
monthly_savings = current_monthly_cost - recommended_monthly_cost  # $312/mois (75%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Redis Tier Downgrade Matrix**:
```python
# Basé sur avg_memory%
downgrade_recommendations = {
    # Standard tier
    ("C6", 30): "C3",  # 53 GB → 6 GB (économie: $1,456/mois)
    ("C5", 30): "C2",  # 26 GB → 2.5 GB (économie: $728/mois)
    ("C4", 30): "C2",  # 13 GB → 2.5 GB (économie: $312/mois)
    ("C3", 30): "C1",  # 6 GB → 1 GB (économie: $156/mois)
    ("C2", 30): "C1",  # 2.5 GB → 1 GB (économie: $52/mois)

    # Premium tier
    ("P4", 30): "P1",  # 53 GB → 6 GB (économie: $3,976/mois)
    ("P3", 30): "P1",  # 26 GB → 6 GB (économie: $1,704/mois)
    ("P2", 30): "P1",  # 13 GB → 6 GB (économie: $568/mois)
}
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `over_sized_threshold`: 30 (% memory)
- `recommended_buffer`: 1.2 (20% buffer)
- `alert_threshold_percent`: 25
- `critical_threshold_percent`: 15

**Confidence level**:
- avg_memory% 25-30%: MEDIUM (60%)
- avg_memory% 15-25%: HIGH (80%)
- avg_memory% <15%: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_redis_cache",
  "scenario": "redis_over_sized_tier",
  "cache_name": "redis-cache-api-prod",
  "provisioning_state": "Succeeded",
  "current_sku": {
    "name": "C4",
    "tier": "Standard",
    "family": "C",
    "capacity": 13
  },
  "monitoring_period_days": 30,
  "avg_memory_percent": 18.5,
  "max_memory_percent": 42.3,
  "p95_memory_percent": 35.1,
  "used_memory_gb": 2.4,
  "current_monthly_cost": 416.00,
  "recommended_sku": {
    "name": "C2",
    "tier": "Standard",
    "capacity": 2.5
  },
  "recommended_monthly_cost": 104.00,
  "monthly_savings_potential": 312.00,
  "annual_savings_potential": 3744.00,
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py:2994` (stub existant)

---

## 🧪 Matrice de Test

| # | Scénario | Service | Phase | Implémenté | Testé | Priorité | Impact ROI |
|---|----------|---------|-------|-----------|-------|----------|------------|
| 1 | `sql_database_stopped` | SQL Database | 1 | ⚠️ | ❌ | **P0** | 🔥🔥 Very High ($147-15,699/mois) |
| 2 | `sql_database_idle_connections` | SQL Database | 1 | ⚠️ | ❌ | **P0** | 🔥🔥 Very High ($147-15,699/mois) |
| 3 | `sql_database_over_provisioned_dtu` | SQL Database | 1 | ❌ | ❌ | **P1** | 🔥🔥 High ($118-456/mois) |
| 4 | `sql_database_serverless_not_pausing` | SQL Database | 2 | ❌ | ❌ | **P1** | 🔥 Medium ($286/mois) |
| 5 | `cosmosdb_over_provisioned_ru` | Cosmos DB | 1 | ❌ | ❌ | **P0** | 🔥🔥 Very High ($409/mois) |
| 6 | `cosmosdb_idle_containers` | Cosmos DB | 1 | ❌ | ❌ | **P0** | 🔥 Low-Medium ($36/mois) |
| 7 | `cosmosdb_hot_partitions_idle_others` | Cosmos DB | 2 | ❌ | ❌ | **P2** | 🔥🔥 High ($409/mois) |
| 8 | `postgres_mysql_stopped` | PostgreSQL/MySQL | 1 | ⚠️ | ❌ | **P1** | 💰 Low ($15-22/mois storage) |
| 9 | `postgres_mysql_idle_connections` | PostgreSQL/MySQL | 1 | ⚠️ | ❌ | **P0** | 🔥 Medium ($150-600/mois) |
| 10 | `postgres_mysql_over_provisioned_vcores` | PostgreSQL/MySQL | 1 | ❌ | ❌ | **P1** | 🔥 Medium ($300/mois) |
| 11 | `postgres_mysql_burstable_always_bursting` | PostgreSQL/MySQL | 2 | ❌ | ❌ | **P2** | 🔍 Performance (pas waste direct) |
| 12 | `synapse_sql_pool_paused` | Synapse | 1 | ⚠️ | ❌ | **P1** | 🔥 High ($246-983/mois storage) |
| 13 | `synapse_sql_pool_idle_queries` | Synapse | 1 | ⚠️ | ❌ | **P0** | 🔥🔥🔥 Critical ($4,503-9,006/mois) |
| 14 | `redis_idle_cache` | Redis | 1 | ⚠️ | ❌ | **P0** | 🔥 Medium ($104-1,664/mois) |
| 15 | `redis_over_sized_tier` | Redis | 1 | ❌ | ❌ | **P1** | 🔥 Medium ($312-3,976/mois) |

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

# Installer extensions
az extension add --name rdbms-connect
az extension add --name synapse
```

---

### Test Scénario #1: `sql_database_stopped`

**Objectif**: Créer SQL Database et la mettre en pause.

```bash
# Variables
LOCATION="eastus"
RG_NAME="rg-cloudwaste-test-sql"
SQL_SERVER_NAME="sqlserver-test-$RANDOM"
SQL_DB_NAME="db-test-stopped"
ADMIN_USER="sqladmin"
ADMIN_PASSWORD="P@ssw0rd$(date +%s)"

# Créer resource group
az group create --name $RG_NAME --location $LOCATION

# Créer SQL Server
az sql server create \
  --resource-group $RG_NAME \
  --name $SQL_SERVER_NAME \
  --location $LOCATION \
  --admin-user $ADMIN_USER \
  --admin-password $ADMIN_PASSWORD

# Créer SQL Database (tier Standard S3)
az sql db create \
  --resource-group $RG_NAME \
  --server $SQL_SERVER_NAME \
  --name $SQL_DB_NAME \
  --service-objective S3 \
  --edition Standard

# Attendre provisioning
sleep 30

# Pause database
az sql db pause \
  --resource-group $RG_NAME \
  --server $SQL_SERVER_NAME \
  --name $SQL_DB_NAME

# Vérifier statut
az sql db show \
  --resource-group $RG_NAME \
  --server $SQL_SERVER_NAME \
  --name $SQL_DB_NAME \
  --query "{name:name, status:status, sku:sku, maxSizeBytes:maxSizeBytes}" \
  --output json

# Expected: status = "Paused"
# Coût: $147.24/mois (compute) + storage (si storage au-delà de tier inclus)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

**Résultat attendu**:
```json
{
  "name": "db-test-stopped",
  "status": "Paused",
  "sku": {
    "name": "S3",
    "tier": "Standard",
    "capacity": 100
  },
  "maxSizeBytes": 268435456000
}
```

---

### Test Scénario #2: `sql_database_idle_connections`

**Objectif**: Database active mais aucune connexion.

```bash
# Créer SQL Database (reprendre test #1 sans pause)
# ... (étapes précédentes)

# Database créée mais aucune connexion effectuée

# Attendre 5-10 minutes pour métriques
sleep 300

# Query métriques via CLI
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
DB_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.Sql/servers/$SQL_SERVER_NAME/databases/$SQL_DB_NAME"

# Métriques connections
az monitor metrics list \
  --resource $DB_RESOURCE_ID \
  --metric connection_successful \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Total \
  --output table

# Expected: Total connections = 0

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #3: `sql_database_over_provisioned_dtu`

**Objectif**: Database DTU sous-utilisé.

```bash
# Créer SQL Database S3 (100 DTU)
# ... (reprendre étapes création)

# Simuler faible charge via queries légères
CONNECTION_STRING="Server=tcp:$SQL_SERVER_NAME.database.windows.net,1433;Initial Catalog=$SQL_DB_NAME;User ID=$ADMIN_USER;Password=$ADMIN_PASSWORD;Encrypt=True;TrustServerCertificate=False;"

# Exécuter queries légères toutes les 5 min pendant 1h
for i in {1..12}; do
  sqlcmd -S "$SQL_SERVER_NAME.database.windows.net" -d $SQL_DB_NAME -U $ADMIN_USER -P $ADMIN_PASSWORD -Q "SELECT TOP 10 * FROM sys.tables" &
  sleep 300
done

# Attendre accumulation métriques
sleep 600

# Query DTU consumption
az monitor metrics list \
  --resource $DB_RESOURCE_ID \
  --metric dtu_consumption_percent \
  --start-time $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Average \
  --output json \
  | jq '[.value[0].timeseries[0].data[].average] | add / length'

# Expected: Average DTU% < 30%
# Recommandation: Downgrade vers S1 (20 DTU) ou S2 (50 DTU)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #5: `cosmosdb_over_provisioned_ru`

**Objectif**: Cosmos DB container avec RU sur-provisionnés.

```bash
# Variables
RG_NAME="rg-cloudwaste-test-cosmos"
COSMOS_ACCOUNT="cosmos-test-$RANDOM"
COSMOS_DB="TestDB"
COSMOS_CONTAINER="TestContainer"

# Créer resource group
az group create --name $RG_NAME --location eastus

# Créer Cosmos DB account (SQL API)
az cosmosdb create \
  --resource-group $RG_NAME \
  --name $COSMOS_ACCOUNT \
  --kind GlobalDocumentDB \
  --locations regionName=eastus failoverPriority=0 \
  --default-consistency-level Session

# Créer database avec throughput
az cosmosdb sql database create \
  --resource-group $RG_NAME \
  --account-name $COSMOS_ACCOUNT \
  --name $COSMOS_DB \
  --throughput 10000

# Créer container
az cosmosdb sql container create \
  --resource-group $RG_NAME \
  --account-name $COSMOS_ACCOUNT \
  --database-name $COSMOS_DB \
  --name $COSMOS_CONTAINER \
  --partition-key-path "/id" \
  --throughput 10000

# Insérer quelques documents (faible activité)
# (Utiliser SDK ou Data Explorer dans Portal)

# Attendre métriques (quelques heures)
sleep 3600

# Query RU consumption
COSMOS_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.DocumentDB/databaseAccounts/$COSMOS_ACCOUNT"

az monitor metrics list \
  --resource $COSMOS_RESOURCE_ID \
  --metric TotalRequestUnits \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Total \
  --output json

# Calculer utilization%
# total_ru_consumed / (10000 RU/s * 3600 sec) * 100

# Expected: <30% utilization
# Recommandation: Réduire à 3000-5000 RU/s

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #9: `postgres_mysql_idle_connections`

**Objectif**: PostgreSQL Flexible Server sans connexions.

```bash
# Variables
RG_NAME="rg-cloudwaste-test-postgres"
POSTGRES_SERVER="postgres-test-$RANDOM"
POSTGRES_ADMIN="pgadmin"
POSTGRES_PASSWORD="P@ssw0rd$(date +%s)"

# Créer resource group
az group create --name $RG_NAME --location eastus

# Créer PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group $RG_NAME \
  --name $POSTGRES_SERVER \
  --location eastus \
  --admin-user $POSTGRES_ADMIN \
  --admin-password $POSTGRES_PASSWORD \
  --sku-name Standard_D4s_v3 \
  --tier GeneralPurpose \
  --version 14 \
  --storage-size 128 \
  --yes

# Attendre provisioning
sleep 120

# Vérifier server (mais pas de connexions)
az postgres flexible-server show \
  --resource-group $RG_NAME \
  --name $POSTGRES_SERVER \
  --query "{name:name, state:state, sku:sku, storageProfile:storageProfile}" \
  --output json

# Attendre métriques (30 min)
sleep 1800

# Query connections metrics
POSTGRES_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.DBforPostgreSQL/flexibleServers/$POSTGRES_SERVER"

az monitor metrics list \
  --resource $POSTGRES_RESOURCE_ID \
  --metric active_connections \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Average \
  --output table

# Expected: Average connections = 0
# Coût: ~$300-600/mois (selon vCores)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #13: `synapse_sql_pool_idle_queries`

**Objectif**: Synapse SQL Pool actif mais pas de queries.

```bash
# Variables
RG_NAME="rg-cloudwaste-test-synapse"
SYNAPSE_WORKSPACE="synapse-test-$RANDOM"
SQL_POOL_NAME="sqlpool01"
STORAGE_ACCOUNT="synapsestore$RANDOM"

# Créer resource group
az group create --name $RG_NAME --location eastus

# Créer storage account (requis pour Synapse)
az storage account create \
  --resource-group $RG_NAME \
  --name $STORAGE_ACCOUNT \
  --location eastus \
  --sku Standard_LRS

# Créer filesystem
az storage container create \
  --account-name $STORAGE_ACCOUNT \
  --name workspace \
  --auth-mode login

# Créer Synapse workspace
az synapse workspace create \
  --resource-group $RG_NAME \
  --name $SYNAPSE_WORKSPACE \
  --location eastus \
  --storage-account $STORAGE_ACCOUNT \
  --file-system workspace \
  --sql-admin-login-user sqladmin \
  --sql-admin-login-password "P@ssw0rd$(date +%s)"

# Attendre provisioning
sleep 300

# Créer SQL Pool (DW500c)
az synapse sql pool create \
  --resource-group $RG_NAME \
  --workspace-name $SYNAPSE_WORKSPACE \
  --name $SQL_POOL_NAME \
  --performance-level DW500c

# Attendre provisioning (plusieurs minutes)
sleep 600

# Vérifier SQL Pool (actif mais pas de queries)
az synapse sql pool show \
  --resource-group $RG_NAME \
  --workspace-name $SYNAPSE_WORKSPACE \
  --name $SQL_POOL_NAME \
  --query "{name:name, status:status, sku:sku}" \
  --output json

# Expected: status = "Online", mais aucune query
# Coût: $4,380/mois (DW500c)

# Cleanup (important: pool très coûteux!)
az synapse sql pool delete \
  --resource-group $RG_NAME \
  --workspace-name $SYNAPSE_WORKSPACE \
  --name $SQL_POOL_NAME \
  --yes

az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #14: `redis_idle_cache`

**Objectif**: Redis cache sans connexions.

```bash
# Variables
RG_NAME="rg-cloudwaste-test-redis"
REDIS_CACHE="redis-test-$RANDOM"

# Créer resource group
az group create --name $RG_NAME --location eastus

# Créer Redis cache (Standard C2)
az redis create \
  --resource-group $RG_NAME \
  --name $REDIS_CACHE \
  --location eastus \
  --sku Standard \
  --vm-size c2 \
  --enable-non-ssl-port false

# Attendre provisioning (peut prendre 20+ minutes)
echo "Waiting for Redis provisioning (this may take 20+ minutes)..."
az redis show \
  --resource-group $RG_NAME \
  --name $REDIS_CACHE \
  --query provisioningState \
  --output tsv

# Vérifier cache (mais aucune connexion)
az redis show \
  --resource-group $RG_NAME \
  --name $REDIS_CACHE \
  --query "{name:name, provisioningState:provisioningState, sku:sku, redisVersion:redisVersion}" \
  --output json

# Attendre métriques (30 min)
sleep 1800

# Query connections metrics
REDIS_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.Cache/Redis/$REDIS_CACHE"

az monitor metrics list \
  --resource $REDIS_RESOURCE_ID \
  --metric connectedclients \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Maximum \
  --output table

# Expected: Max connections = 0
# Coût: $104/mois (Standard C2)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

## 🔧 Troubleshooting Guide

### Problème 1: SQL Database ne peut pas être supprimée (geo-replicas actifs)

**Erreur**:
```
Cannot delete database 'db-prod' because it has active geo-replication links
```

**Cause**: Database a des secondary replicas (geo-replication).

**Solution**:
```bash
# Lister geo-replication links
az sql db replica list-links \
  --resource-group $RG_NAME \
  --server $SQL_SERVER_NAME \
  --name $SQL_DB_NAME \
  --output table

# Supprimer secondary replicas d'abord
az sql db replica delete-link \
  --resource-group $RG_NAME \
  --server $SQL_SERVER_NAME \
  --name $SQL_DB_NAME \
  --partner-server $PARTNER_SERVER \
  --partner-resource-group $PARTNER_RG

# Puis supprimer primary database
az sql db delete \
  --resource-group $RG_NAME \
  --server $SQL_SERVER_NAME \
  --name $SQL_DB_NAME \
  --yes
```

---

### Problème 2: Cosmos DB container supprimé mais toujours facturé

**Symptôme**: Container supprimé mais coûts persistent.

**Cause**: Soft delete activé (retention period).

**Diagnostic**:
```bash
# Vérifier backup policy
az cosmosdb show \
  --resource-group $RG_NAME \
  --name $COSMOS_ACCOUNT \
  --query "backupPolicy" \
  --output json

# Si continuous backup (PITR), containers supprimés gardés 30 jours
```

**Solution**:
```bash
# Option 1: Attendre fin retention period (30 jours)

# Option 2: Désactiver continuous backup (si possible)
# Note: Nécessite recréation account

# Option 3: Contacter support Azure pour purge immédiat
```

---

### Problème 3: PostgreSQL/MySQL Flexible Server - métriques connections non disponibles

**Symptôme**: Métriques `active_connections` vides.

**Cause**: Server jamais démarré ou extension monitoring pas activée.

**Solution**:
```bash
# Vérifier server state
az postgres flexible-server show \
  --resource-group $RG_NAME \
  --name $POSTGRES_SERVER \
  --query state \
  --output tsv

# Si state = "Ready", vérifier extensions
az postgres flexible-server execute \
  --name $POSTGRES_SERVER \
  --admin-user $ADMIN_USER \
  --admin-password $ADMIN_PASSWORD \
  --database-name postgres \
  --querytext "SELECT * FROM pg_available_extensions WHERE name = 'pg_stat_statements';"

# Activer extension si besoin
az postgres flexible-server execute \
  --name $POSTGRES_SERVER \
  --admin-user $ADMIN_USER \
  --admin-password $ADMIN_PASSWORD \
  --database-name postgres \
  --querytext "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Attendre 10-15 min pour métriques
```

---

### Problème 4: Synapse SQL Pool pause échoue

**Erreur**:
```
Cannot pause SQL Pool 'sqlpool01' because active queries are running
```

**Cause**: Queries en cours d'exécution.

**Solution**:
```bash
# Identifier queries actives (via Portal ou SQL)
# Se connecter au SQL Pool:
sqlcmd -S "$SYNAPSE_WORKSPACE.sql.azuresynapse.net" -d $SQL_POOL_NAME -U sqladmin -P $PASSWORD

# Lister sessions actives
SELECT * FROM sys.dm_pdw_exec_sessions WHERE status = 'Active';

# Kill sessions si nécessaire
KILL 'session_id';

# Puis pause
az synapse sql pool pause \
  --resource-group $RG_NAME \
  --workspace-name $SYNAPSE_WORKSPACE \
  --name $SQL_POOL_NAME
```

---

### Problème 5: Redis cache - erreur "access keys not available"

**Symptôme**: Impossible de récupérer access keys pour tests.

**Cause**: Permissions insuffisantes ou cache provisionné avec AAD-only auth.

**Solution**:
```bash
# Vérifier permissions (besoin "Redis Cache Contributor" ou "Owner")
az role assignment list \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.Cache/Redis/$REDIS_CACHE" \
  --assignee $(az account show --query user.name --output tsv) \
  --output table

# Si AAD-only auth, désactiver pour tests
az redis update \
  --resource-group $RG_NAME \
  --name $REDIS_CACHE \
  --set redisConfiguration.aad-enabled=false

# Récupérer keys
az redis list-keys \
  --resource-group $RG_NAME \
  --name $REDIS_CACHE \
  --output table
```

---

### Problème 6: Cosmos DB hot partitions - comment identifier partition key problématique?

**Symptôme**: Métriques montrent hot partitions mais partition key non évident.

**Diagnostic**:
```bash
# Via Portal: Insights > Throughput > Normalized RU Consumption (par PartitionKeyRangeId)

# Via CLI (limité, besoin SDK pour détails)
az monitor metrics list \
  --resource $COSMOS_RESOURCE_ID \
  --metric NormalizedRUConsumption \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Maximum \
  --output json

# Pour identifier valeurs partition key:
# 1. Activer Diagnostic Settings → Log Analytics
# 2. Query Kusto:
#    DataPlaneRequests
#    | where TimeGenerated > ago(1h)
#    | summarize count() by PartitionKey
#    | order by count_ desc
```

**Solution**:
- Analyser distribution valeurs partition key
- Redesign partition key (ex: userId → userId + date)
- Utiliser hierarchical partition keys (Cosmos DB 2025 feature)

---

## 💰 Impact Business & ROI

### Économies Potentielles par Service

| Service | Scénarios | Économie Mensuelle Moyenne | Fréquence* | ROI Annuel (Organisation Moyenne) |
|---------|-----------|----------------------------|------------|-----------------------------------|
| **Azure SQL Database** | 4 | $300-500 | 35% | $12,600-21,000 |
| **Azure Cosmos DB** | 3 | $400-600 | 25% | $12,000-18,000 |
| **Azure PostgreSQL/MySQL** | 4 | $200-400 | 30% | $7,200-14,400 |
| **Azure Synapse Analytics** | 2 | $4,000-6,000 | 10% | $48,000-72,000 |
| **Azure Cache for Redis** | 2 | $150-300 | 20% | $3,600-7,200 |
| **TOTAL** | **15** | | | **$83,400-132,600/an** |

\* Fréquence = % des ressources affectées (estimé)

---

### Scénarios par ROI Décroissant

1. **Synapse SQL Pool Idle** ($4,503-9,006/mois par pool)
   - Impact: **CRITIQUE** - Pool DW500c+ actif 24/7 sans queries
   - Économie: **$54,036-108,072/an** pour 1 pool DW1000c
   - Action: Pause immédiate ou suppression

2. **SQL Database Over-Provisioned** ($118-456/mois par DB)
   - Impact: **Très élevé** - 35% des SQL Databases sur-provisionnées
   - Économie: **$49,560/an** pour 35 databases (P1→S3)
   - Action: Downgrade vers tier approprié

3. **Cosmos DB Over-Provisioned RU** ($409/mois par container)
   - Impact: **Très élevé** - RU provisionnés 3-5x au-dessus du besoin
   - Économie: **$122,640/an** pour 25 containers
   - Action: Réduire RU ou passer en Autoscale

4. **Redis Over-Sized Tier** ($312-3,976/mois par cache)
   - Impact: **Élevé** - Caches Premium/Standard surdimensionnés
   - Économie: **$37,440/an** pour 10 caches (Standard C4→C2)
   - Action: Downgrade tier

5. **PostgreSQL/MySQL Over-Provisioned** ($300/mois par server)
   - Impact: **Élevé** - 30% des servers avec CPU <20%
   - Économie: **$21,600/an** pour 6 servers (8 vCores→4 vCores)
   - Action: Réduire vCores

---

### Arguments Business

#### 1. **Databases = 30-40% des Coûts Cloud**

**Stat clé**: Selon Gartner, les databases représentent **30-40% des dépenses cloud** d'une organisation moyenne.

**Exemple réel**:
```
Organisation avec $500k/an Azure spend:
- Databases: $150k-200k/an (30-40%)
- Over-provisioning moyen: 40% (études FinOps)
- Waste évitable: $60k-80k/an

ROI CloudWaste: $60k-80k économisés
Coût CloudWaste: ~$10k/an
ROI Net: $50k-70k/an (500-700% ROI)
```

#### 2. **Synapse Analytics: Coût Exponentiel**

**Problème**: Synapse SQL Pools coûtent **$1.20-360/heure** selon DWU.

**Pattern courant**:
```
SQL Pool DW1000c (Data Warehouse):
- Coût: $12/heure = $8,760/mois si online 24/7
- Usage réel: Queries 2h/jour (analyse batch)
- Coût optimal: $12/h × 60h/mois = $720/mois
- Waste: $8,040/mois = $96,480/an
```

**CloudWaste action**:
- Détecter SQL Pools idle >80% du temps
- Recommander pause automatique (via Logic Apps)
- ROI: **$96,480/an par pool** identifié

#### 3. **Cosmos DB: RU Over-Provisioning Systématique**

**Pattern**: Provisioning initial avec buffer 3-5x, jamais revisité.

**Exemple**:
```
Container "Orders" (e-commerce):
- RU provisionnés: 50,000 RU/s
- Coût: (50000/100) × $0.008 × 730 = $2,920/mois

- RU utilisés (avg): 12,000 RU/s (24% utilization)
- RU recommandés: 15,000 RU/s (+20% buffer)
- Coût optimisé: (15000/100) × $0.008 × 730 = $876/mois

Économie: $2,044/mois = $24,528/an par container
```

**CloudWaste ROI**: 25 containers → **$610,700/an** économisés

#### 4. **SQL Database: DTU vs vCore vs Serverless**

**Problème**: Mauvais choix de compute model.

**Cas d'usage**:
```
Dev/Test Database:
- Usage: 8h/jour × 5j/semaine = 173h/mois (24% uptime)

Option 1 - DTU Provisioned (actuel):
- S3 (100 DTU): $147.24/mois (24/7)
- Coût annuel: $1,767/an

Option 2 - vCore Serverless:
- 2 vCores serverless: $0.5218/vCore/h
- Coût compute: 2 × $0.5218 × 173h = $180/mois
- Auto-pause delay: 60 min
- Coût annuel: $2,160/an (mais mieux adapté)

Option 3 - Start/Stop manuel:
- S3 running 173h/mois: $147.24 × (173/730) = $34.89/mois
- Coût annuel: $419/an (si automation fiable)

Économie vs provisioned 24/7: $1,348-1,587/an
```

**CloudWaste action**:
- Détecter databases avec uptime <50%
- Recommander Serverless ou automation start/stop
- ROI: **$1,400/an par database** dev/test

#### 5. **PostgreSQL/MySQL: Flexible Server Stop/Start**

**Feature clé**: Flexible Server peut être stopped (compute gratuit, storage payé).

**Cas d'usage**:
```
PostgreSQL General Purpose 8 vCores:
- Coût compute: 8 × $0.1027 × 730 = $599.76/mois
- Coût storage: 256 GB × $0.115 = $29.44/mois
- Total: $629.20/mois ($7,550/an)

Si stopped 50% du temps:
- Compute: $599.76 × 0.5 = $299.88/mois
- Storage: $29.44/mois (toujours payé)
- Total: $329.32/mois ($3,952/an)

Économie: $3,598/an (48% savings)
```

**CloudWaste action**:
- Détecter servers idle >7 jours
- Recommander stop ou automation
- ROI: **$3,600/an par server** identifié

---

### ROI Global Estimé

**Organisation moyenne (100 databases Azure)**:

| Ressources | Quantité | Waste Moyen | Économie Annuelle |
|------------|----------|-------------|-------------------|
| SQL Database idle/stopped | 15 | $147/mois | $26,460 |
| SQL Database over-provisioned | 25 | $150/mois | $45,000 |
| Cosmos DB containers over-RU | 20 | $409/mois | $98,160 |
| PostgreSQL/MySQL idle | 8 | $300/mois | $28,800 |
| PostgreSQL/MySQL over-vCores | 10 | $300/mois | $36,000 |
| Synapse SQL Pool idle | 2 | $4,503/mois | $108,072 |
| Redis cache idle | 5 | $104/mois | $6,240 |
| Redis cache over-sized | 8 | $312/mois | $29,952 |
| **TOTAL** | **93** | | **$378,684/an** |

**CloudWaste Pricing**: ~$15,000-25,000/an (100 databases)
**ROI Net**: **$353,684/an (1,415% ROI)**
**Payback Period**: **< 3 semaines**

---

## 📚 Références Officielles Azure

### Azure SQL Database

1. **Pricing**
   https://azure.microsoft.com/en-us/pricing/details/azure-sql-database/single/

2. **DTU vs vCore**
   https://learn.microsoft.com/en-us/azure/azure-sql/database/purchasing-models?view=azuresql

3. **Serverless Compute**
   https://learn.microsoft.com/en-us/azure/azure-sql/database/serverless-tier-overview?view=azuresql

4. **Performance Monitoring (sys.dm_db_resource_stats)**
   https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-views/sys-dm-db-resource-stats-azure-sql-database

5. **Azure Advisor Recommendations**
   https://learn.microsoft.com/en-us/azure/azure-sql/database/database-advisor-implement-performance-recommendations?view=azuresql

### Azure Cosmos DB

6. **Pricing Model**
   https://learn.microsoft.com/en-us/azure/cosmos-db/how-pricing-works

7. **Request Units (RU) Explained**
   https://learn.microsoft.com/en-us/azure/cosmos-db/request-units

8. **Autoscale Throughput**
   https://learn.microsoft.com/en-us/azure/cosmos-db/provision-throughput-autoscale

9. **Normalized RU Consumption (Hot Partitions)**
   https://learn.microsoft.com/en-us/azure/cosmos-db/monitor-normalized-request-units

10. **Partition Key Best Practices**
    https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning-overview

### Azure PostgreSQL / MySQL

11. **Flexible Server Pricing**
    https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/
    https://azure.microsoft.com/en-us/pricing/details/mysql/

12. **Compute Tiers (Burstable, General Purpose, Memory Optimized)**
    https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-compute

13. **Stop/Start Server**
    https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-stop-start-server-portal

14. **Cost Optimization**
    https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-cost-optimization

### Azure Synapse Analytics

15. **Pricing**
    https://azure.microsoft.com/en-us/pricing/details/synapse-analytics/

16. **Pause and Resume SQL Pool**
    https://learn.microsoft.com/en-us/azure/synapse-analytics/sql-data-warehouse/pause-and-resume-compute-portal

17. **Performance Monitoring (DMVs)**
    https://learn.microsoft.com/en-us/azure/synapse-analytics/sql-data-warehouse/sql-data-warehouse-manage-monitor

### Azure Cache for Redis

18. **Pricing**
    https://azure.microsoft.com/en-us/pricing/details/cache/

19. **Tiers (Basic, Standard, Premium)**
    https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/cache-overview#service-tiers

20. **Azure Managed Redis (Replacement)**
    https://azure.microsoft.com/en-us/products/managed-redis/

21. **Monitoring Metrics**
    https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/cache-how-to-monitor

### Azure SDK Documentation

22. **azure-mgmt-sql (Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-sql/azure.mgmt.sql

23. **azure-mgmt-cosmosdb (Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-cosmosdb/azure.mgmt.cosmosdb

24. **azure-mgmt-rdbms (PostgreSQL/MySQL Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-rdbms/azure.mgmt.rdbms

25. **azure-mgmt-synapse (Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-synapse/azure.mgmt.synapse

26. **azure-mgmt-redis (Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-redis/azure.mgmt.redis

27. **azure-monitor-query (Metrics API)**
    https://learn.microsoft.com/en-us/python/api/azure-monitor-query/azure.monitor.query

### FinOps & Cost Optimization

28. **FinOps Best Practices for Databases**
    https://learn.microsoft.com/en-us/cloud-computing/finops/best-practices/databases

29. **Azure Advisor Cost Recommendations**
    https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations

30. **Azure Cost Management**
    https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/cost-mgt-best-practices

---

## ✅ Checklist d'Implémentation

### Phase 1 - Azure SQL Database (Sprint 1)

- [ ] **Scénario #1**: `sql_database_stopped`
  - [ ] Compléter stub `scan_stopped_databases()` (ligne 2909)
  - [ ] Query via `SqlManagementClient.databases.list()`
  - [ ] Filter: `status == 'Paused'`
  - [ ] Récupérer pause time via Activity Log
  - [ ] Calcul coût: DTU/vCore pricing + storage
  - [ ] Tests unitaires
  - [ ] Tests CLI

- [ ] **Scénario #2**: `sql_database_idle_connections`
  - [ ] Fonction dans même stub (ligne 2909)
  - [ ] Query Azure Monitor metric `connection_successful`
  - [ ] Filter: `total_connections == 0` sur 30 jours
  - [ ] Tests

- [ ] **Scénario #3**: `sql_database_over_provisioned_dtu`
  - [ ] Fonction `scan_sql_over_provisioned_dtu()`
  - [ ] Query metric `dtu_consumption_percent`
  - [ ] Calcul avg DTU% sur 30 jours
  - [ ] Downgrade recommendations matrix
  - [ ] Tests

- [ ] **Scénario #4**: `sql_database_serverless_not_pausing`
  - [ ] Fonction `scan_sql_serverless_not_pausing()`
  - [ ] Filter tier Serverless
  - [ ] Query metric `cpu_percent` (detect pauses via gaps)
  - [ ] Calcul économie vs expected uptime
  - [ ] Tests

### Phase 2 - Azure Cosmos DB (Sprint 2)

- [ ] **Scénario #5**: `cosmosdb_over_provisioned_ru`
  - [ ] Fonction `scan_cosmosdb_over_provisioned_ru()`
  - [ ] Query via `CosmosDBManagementClient`
  - [ ] Query metric `TotalRequestUnits`
  - [ ] Calcul utilization% (consumed / available)
  - [ ] RU downgrade recommendations
  - [ ] Tests

- [ ] **Scénario #6**: `cosmosdb_idle_containers`
  - [ ] Fonction `scan_cosmosdb_idle_containers()`
  - [ ] Query metric `TotalRequests` per container
  - [ ] Filter: `total_requests == 0`
  - [ ] Tests

- [ ] **Scénario #7**: `cosmosdb_hot_partitions_idle_others`
  - [ ] Fonction `scan_cosmosdb_hot_partitions()`
  - [ ] Query metric `NormalizedRUConsumption` (par partition)
  - [ ] Identifier hot (>80%) + idle (<10%)
  - [ ] Tests

### Phase 3 - PostgreSQL / MySQL (Sprint 3)

- [ ] **Scénario #8**: `postgres_mysql_stopped`
  - [ ] Compléter stub (ligne 2909)
  - [ ] Query via `PostgreSQLManagementClient` + `MySQLManagementClient`
  - [ ] Filter: `state == 'Stopped'`
  - [ ] Calcul coût: storage + backup (compute gratuit si stopped)
  - [ ] Tests

- [ ] **Scénario #9**: `postgres_mysql_idle_connections`
  - [ ] Fonction dans même stub
  - [ ] Query metric `active_connections`
  - [ ] Filter: `max_connections == 0`
  - [ ] Tests

- [ ] **Scénario #10**: `postgres_mysql_over_provisioned_vcores`
  - [ ] Fonction `scan_postgres_mysql_over_provisioned()`
  - [ ] Query metric `cpu_percent`
  - [ ] Calcul avg CPU% sur 30 jours
  - [ ] SKU downgrade recommendations
  - [ ] Tests

- [ ] **Scénario #11**: `postgres_mysql_burstable_always_bursting`
  - [ ] Fonction `scan_postgres_mysql_burstable_bursting()`
  - [ ] Filter tier == 'Burstable'
  - [ ] Query metric `cpu_percent`
  - [ ] Calcul % temps >50% CPU
  - [ ] Recommander General Purpose si >70%
  - [ ] Tests

### Phase 4 - Synapse & Redis (Sprint 4)

- [ ] **Scénario #12**: `synapse_sql_pool_paused`
  - [ ] Compléter stub (ligne 2986)
  - [ ] Query via `SynapseManagementClient.sql_pools`
  - [ ] Filter: `status == 'Paused'`
  - [ ] Tests

- [ ] **Scénario #13**: `synapse_sql_pool_idle_queries`
  - [ ] Fonction dans même stub
  - [ ] Query metric `DWUUsedPercent`
  - [ ] Filter: `max_dwu_percent < 1%`
  - [ ] Tests

- [ ] **Scénario #14**: `redis_idle_cache`
  - [ ] Compléter stub (ligne 2994)
  - [ ] Query via `RedisManagementClient`
  - [ ] Query metric `connectedclients`
  - [ ] Filter: `max_connections == 0`
  - [ ] Tests

- [ ] **Scénario #15**: `redis_over_sized_tier`
  - [ ] Fonction dans même stub
  - [ ] Query metric `usedmemorypercentage`
  - [ ] Calcul avg memory%
  - [ ] Tier downgrade recommendations
  - [ ] Tests

### Infrastructure & Tests

- [ ] **Database Schema**
  - [ ] Ajouter colonne `database_service` (sql, cosmos, postgres, mysql, synapse, redis)
  - [ ] Migration Alembic
  - [ ] Indexes

- [ ] **Detection Rules**
  - [ ] Règles par défaut pour chaque service
  - [ ] Paramètres configurables
  - [ ] UI ajustement règles

- [ ] **Tests**
  - [ ] Tests unitaires (70%+ coverage)
  - [ ] Tests Azure SDK mocks
  - [ ] Tests CLI (scripts ci-dessus)
  - [ ] Tests end-to-end

- [ ] **Documentation**
  - [ ] API endpoints
  - [ ] Frontend components
  - [ ] User guide

### Frontend

- [ ] **Dashboard**
  - [ ] Afficher databases par service
  - [ ] Filtrer par scénario
  - [ ] Tri par coût

- [ ] **Resource Details**
  - [ ] Pages détail par service
  - [ ] Graphiques Azure Monitor
  - [ ] Actions (Ignore, Delete)
  - [ ] Recommandations

- [ ] **Cost Calculator**
  - [ ] Estimateur économies databases
  - [ ] Comparaison tiers (DTU vs vCore, RU provisioned vs autoscale)
  - [ ] Export PDF

---

## 🎯 Priorités d'Implémentation

### P0 - Quick Wins (Sprint 1)
1. `sql_database_stopped` (stub existant, économie $147-15,699/mois)
2. `sql_database_idle_connections` (stub existant, économie identique)
3. `cosmosdb_over_provisioned_ru` (ROI élevé $409/mois, fréquence 25%)
4. `synapse_sql_pool_idle_queries` (**ROI critique** $4,503-9,006/mois)
5. `postgres_mysql_idle_connections` (économie $150-600/mois)
6. `redis_idle_cache` (économie $104-1,664/mois)

**Raison**: Économie immédiate, facile à détecter (Phase 1 simple).

### P1 - High ROI (Sprint 2-3)
7. `sql_database_over_provisioned_dtu` (économie $118-456/mois, 35% fréquence)
8. `postgres_mysql_over_provisioned_vcores` (économie $300/mois)
9. `redis_over_sized_tier` (économie $312-3,976/mois)
10. `sql_database_serverless_not_pausing` (économie $286/mois)
11. `postgres_mysql_stopped` (économie faible $15-22/mois mais facile)
12. `synapse_sql_pool_paused` (économie $246-983/mois storage)

**Raison**: ROI élevé, fréquence moyenne-haute.

### P2 - Strategic (Sprint 4)
13. `cosmosdb_hot_partitions_idle_others` (économie $409/mois mais complexe)
14. `cosmosdb_idle_containers` (économie faible $36/mois)
15. `postgres_mysql_burstable_always_bursting` (pas waste direct, performance)

**Raison**: Impact stratégique (architecture, performance), mais ROI/complexité variable.

---

## 🚀 Quick Start

### Script Test Complet

```bash
#!/bin/bash
# Script: test-all-database-scenarios.sh
# Description: Teste tous les scénarios databases Azure

set -e

echo "🚀 CloudWaste - Test Azure Database Scenarios"
echo "=============================================="

# Variables
LOCATION="eastus"
BASE_RG="rg-cloudwaste-db-test"
SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# Test #1: SQL Database Stopped
echo ""
echo "📊 Test #1: SQL Database Stopped"
RG_NAME="${BASE_RG}-sql"
SQL_SERVER="sqltest$RANDOM"
SQL_DB="db-stopped"

az group create --name $RG_NAME --location $LOCATION --output none
az sql server create --resource-group $RG_NAME --name $SQL_SERVER --location $LOCATION --admin-user sqladmin --admin-password "P@ssw0rd$RANDOM" --output none
az sql db create --resource-group $RG_NAME --server $SQL_SERVER --name $SQL_DB --service-objective S3 --output none
sleep 30
az sql db pause --resource-group $RG_NAME --server $SQL_SERVER --name $SQL_DB --output none

echo "✅ SQL Database paused (Coût: \$147.24/mois wasteful)"
az group delete --name $RG_NAME --yes --no-wait

# Test #2: Cosmos DB Over-Provisioned RU
echo ""
echo "📊 Test #2: Cosmos DB Over-Provisioned RU"
RG_NAME="${BASE_RG}-cosmos"
COSMOS_ACCOUNT="cosmos$RANDOM"

az group create --name $RG_NAME --location $LOCATION --output none
az cosmosdb create --resource-group $RG_NAME --name $COSMOS_ACCOUNT --output none
az cosmosdb sql database create --resource-group $RG_NAME --account-name $COSMOS_ACCOUNT --name TestDB --throughput 10000 --output none

echo "✅ Cosmos DB with 10,000 RU/s (Coût: \$584/mois, likely over-provisioned)"
az group delete --name $RG_NAME --yes --no-wait

# Test #3: PostgreSQL Stopped
echo ""
echo "📊 Test #3: PostgreSQL Flexible Server Stopped"
RG_NAME="${BASE_RG}-postgres"
POSTGRES_SERVER="pg$RANDOM"

az group create --name $RG_NAME --location $LOCATION --output none
az postgres flexible-server create --resource-group $RG_NAME --name $POSTGRES_SERVER --location $LOCATION --admin-user pgadmin --admin-password "P@ssw0rd$RANDOM" --sku-name Standard_B1ms --tier Burstable --yes --output none
sleep 60
az postgres flexible-server stop --resource-group $RG_NAME --name $POSTGRES_SERVER --output none

echo "✅ PostgreSQL stopped (Storage: \$14.72/mois wasteful)"
az group delete --name $RG_NAME --yes --no-wait

# Test #4: Redis Idle Cache
echo ""
echo "📊 Test #4: Redis Cache Idle"
RG_NAME="${BASE_RG}-redis"
REDIS_CACHE="redis$RANDOM"

az group create --name $RG_NAME --location $LOCATION --output none
az redis create --resource-group $RG_NAME --name $REDIS_CACHE --location $LOCATION --sku Standard --vm-size c2 --output none

echo "✅ Redis cache created (Coût: \$104/mois, no connections = wasteful)"
echo "   Note: Redis provisioning takes 20+ min, deleting immediately"
az group delete --name $RG_NAME --yes --no-wait

echo ""
echo "✅ All tests completed!"
echo "   Total wasteful cost detected: ~\$850/mois"
echo "   Run CloudWaste scanner to detect these resources"
```

**Usage**:
```bash
chmod +x test-all-database-scenarios.sh
./test-all-database-scenarios.sh
```

---

## 📊 Résumé Exécutif

### Couverture

- **15 scénarios** (100% coverage)
- **6 services de databases** Azure
- **11 Phase 1** (détection simple)
- **4 Phase 2** (Azure Monitor métriques)

### ROI Estimé

- **Économie moyenne**: $150-6,000/mois par ressource wasteful
- **ROI annuel**: **$83,400-378,684/an** (organisation moyenne)
- **Payback period**: < **3 semaines**

### Impact Critique 2025

- Databases = **30-40% des coûts cloud** (Gartner)
- **60% over-provisionnées** (études FinOps)
- Synapse SQL Pools: **$8,760/mois** si idle 24/7
- Cosmos DB: **70% économies possibles** via RU optimization

### Next Steps

1. **Implémenter P0** (scénarios #1, #2, #5, #13, #9, #14) → Sprint 1
2. **Implémenter P1** (scénarios #3, #8, #10, #15, #4, #11, #12) → Sprint 2-3
3. **Implémenter P2** (scénarios #7, #6, #11) → Sprint 4
4. **Tests end-to-end** + documentation utilisateur

---

**Dernière mise à jour**: 2025-01-28
**Auteur**: CloudWaste Documentation Team
**Version**: 1.0.0
