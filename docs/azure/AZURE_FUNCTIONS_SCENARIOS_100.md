# 📊 CloudWaste - Couverture 100% Azure Functions

## 🎯 Scénarios Couverts (10/10 = 100%)

> **Contexte 2025**: Azure Functions est le service **serverless FaaS** d'Azure avec **3 modèles de pricing** (Consumption, Premium, Dedicated). **50% des Function Apps Premium sont idle ou sous-utilisées** selon les études FinOps. Le choix du mauvais plan génère jusqu'à **$3,000/mois de waste** par application. **Premium plan coûte $388/mois minimum** (toujours actif) vs **Consumption $0 idle** (pay-per-execution).

### Phase 1 - Détection Simple (7 scénarios)

#### 1. `functions_never_invoked` - Function App jamais invoquée depuis création

**Détection**: Function App sans aucune invocation depuis sa création.

**Logique**:
```python
from azure.mgmt.web import WebSiteManagementClient

web_client = WebSiteManagementClient(credential, subscription_id)

for function_app in web_client.web_apps.list():
    # Filtrer Function Apps (kind = "functionapp")
    if function_app.kind and 'functionapp' in function_app.kind.lower():
        # Vérifier invocations via Application Insights
        # Ou via metrics si disponible

        app_insights_instrumentation_key = get_app_insights_key(function_app)

        if app_insights_instrumentation_key:
            # Query total invocations since creation
            total_invocations = query_total_invocations(
                app_insights_instrumentation_key,
                function_app.created_time
            )

            # Si 0 invocations
            if total_invocations == 0:
                age_days = (datetime.now() - function_app.created_time).days

                if age_days >= min_age_days:
                    flag_as_wasteful(function_app)
```

**Calcul coût**:
```python
# Hosting plan type
hosting_plan = get_hosting_plan(function_app)

if 'ElasticPremium' in hosting_plan.sku.tier:
    # Premium plan
    sku_name = hosting_plan.sku.name  # EP1, EP2, EP3

    pricing_premium = {
        "EP1": 0.532,   # $/heure = $388/mois
        "EP2": 1.064,   # $/heure = $776/mois
        "EP3": 2.128,   # $/heure = $1,553/mois
    }

    hourly_cost = pricing_premium.get(sku_name, 0.532)
    monthly_cost = hourly_cost * 730  # Toujours actif (minimum 1 instance)

elif hosting_plan.sku.tier == 'Dynamic':
    # Consumption plan
    # Coût = 0 si jamais invoqué (dans free grant)
    monthly_cost = 0

else:
    # Dedicated (App Service Plan)
    # B1, S1, P1V2, etc.
    monthly_cost = get_app_service_plan_cost(hosting_plan.sku)

already_wasted = monthly_cost * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (35%) - Peut être en développement
- 30-60 jours: MEDIUM (70%) - Probablement oublié
- 60-90 jours: HIGH (85%) - Orphelin confirmé
- >90 jours: CRITICAL (98%) - Définitivement wasteful

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_never_invoked",
  "function_app_name": "func-legacy-api",
  "resource_group": "rg-functions-prod",
  "location": "eastus",
  "kind": "functionapp,linux",
  "hosting_plan_name": "ASP-premium-eastus",
  "hosting_plan_sku": {
    "name": "EP1",
    "tier": "ElasticPremium",
    "capacity": 1
  },
  "runtime_stack": "python",
  "runtime_version": "3.11",
  "created_date": "2024-08-01T10:00:00Z",
  "age_days": 150,
  "total_invocations": 0,
  "monthly_cost_usd": 388.00,
  "already_wasted_usd": 1940.00,
  "recommendation": "Delete function app or migrate to Consumption plan",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:3073` (stub existant)

---

#### 2. `functions_premium_plan_idle` - Premium Plan avec très peu d'invocations

**Détection**: Function App sur Premium plan avec <100 invocations/mois.

**Logique**:
```python
# Function App sur Premium plan
if 'ElasticPremium' in hosting_plan.sku.tier:
    # Query invocations last 30 days
    invocations_last_30_days = query_invocations_count(
        function_app,
        timedelta(days=30)
    )

    # Threshold très bas (100 invocations/mois)
    if invocations_last_30_days < low_invocation_threshold:
        # Premium plan wasteful, devrait être Consumption

        # Calculer économie vs Consumption
        current_cost = calculate_premium_cost(hosting_plan)
        consumption_cost = calculate_consumption_cost(
            invocations_last_30_days,
            avg_memory_mb=512,
            avg_duration_sec=1
        )

        monthly_savings = current_cost - consumption_cost

        flag_as_wasteful(function_app, monthly_savings)
```

**Calcul coût**:
```python
# Coût Premium actuel
sku_name = hosting_plan.sku.name  # EP1
hourly_cost = 0.532  # EP1
monthly_cost_premium = hourly_cost * 730  # $388/mois

# Coût Consumption alternatif
invocations = 100  # invocations/mois
avg_memory_gb = 0.512  # 512 MB
avg_duration_sec = 1

# Executions cost
execution_cost = (invocations / 1_000_000) * 0.20  # $0.00002

# GB-seconds cost
gb_seconds = invocations * avg_memory_gb * avg_duration_sec  # 51.2 GB-s
gb_seconds_cost = gb_seconds * 0.000016  # $0.00082

# Total Consumption cost
monthly_cost_consumption = execution_cost + gb_seconds_cost  # ~$0.0008 (FREE GRANT)

# Économie potentielle
monthly_savings = monthly_cost_premium - monthly_cost_consumption  # $388/mois (99.9%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `low_invocation_threshold`: 100 (invocations/mois)
- `monitoring_period_days`: 30 (défaut)
- `alert_threshold_invocations`: 500
- `critical_threshold_invocations`: 100

**Confidence level**:
- invocations 100-500: MEDIUM (65%) - Peut avoir pics
- invocations 50-100: HIGH (85%) - Clairement sous-utilisé
- invocations <50: CRITICAL (98%) - Quasi idle

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_premium_plan_idle",
  "function_app_name": "func-webhook-prod",
  "hosting_plan_name": "ASP-premium-prod",
  "hosting_plan_sku": {
    "name": "EP1",
    "tier": "ElasticPremium",
    "capacity": 1
  },
  "monitoring_period_days": 30,
  "total_invocations": 75,
  "avg_invocations_per_day": 2.5,
  "avg_memory_mb": 512,
  "avg_duration_seconds": 0.8,
  "current_monthly_cost": 388.00,
  "consumption_equivalent_cost": 0.0006,
  "monthly_savings_potential": 387.99,
  "annual_savings_potential": 4655.88,
  "recommendation": "Migrate to Consumption plan",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py:3073` (stub existant)

---

#### 3. `functions_consumption_over_allocated_memory` - Memory surdimensionnée sur Consumption

**Détection**: Function configurée avec >1 GB memory mais utilisation réelle <50%.

**Logique**:
```python
# Consumption plan
if hosting_plan.sku.tier == 'Dynamic':
    # Pour chaque function dans l'app
    functions = web_client.web_apps.list_functions(
        resource_group_name=rg_name,
        name=function_app.name
    )

    for function in functions:
        # Récupérer configuration memory (via host.json ou function.json)
        configured_memory_mb = get_function_memory_config(function)  # ex: 1536 MB

        # Query utilization réelle via Application Insights
        actual_memory_used_mb = query_avg_memory_usage(function)  # ex: 600 MB

        utilization_percent = (actual_memory_used_mb / configured_memory_mb) * 100

        # Si <50% utilisé
        if utilization_percent < memory_utilization_threshold:
            # Over-allocated
            recommended_memory_mb = int(actual_memory_used_mb * 1.5)  # +50% buffer

            flag_as_wasteful(function, configured_memory_mb, recommended_memory_mb)
```

**Calcul coût**:
```python
# Exemple: 10,000 invocations/mois
invocations = 10_000
avg_duration_sec = 2

# Memory actuelle configurée
configured_memory_gb = 1.5  # 1536 MB

# GB-seconds actuel
gb_seconds_current = invocations * configured_memory_gb * avg_duration_sec  # 30,000 GB-s
cost_current = gb_seconds_current * 0.000016  # $0.48/mois

# Memory recommandée (basé sur 600 MB utilisés + 50% buffer = 900 MB)
recommended_memory_gb = 0.9  # 900 MB

# GB-seconds optimisé
gb_seconds_optimized = invocations * recommended_memory_gb * avg_duration_sec  # 18,000 GB-s
cost_optimized = gb_seconds_optimized * 0.000016  # $0.288/mois

# Économie potentielle
monthly_savings = cost_current - cost_optimized  # $0.192/mois (40%)

# À grande échelle (1M invocations/mois)
# Économie: $19.20/mois

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `memory_utilization_threshold`: 50 (%)
- `monitoring_period_days`: 30 (défaut)
- `recommended_buffer`: 1.5 (50% buffer)
- `alert_threshold_percent`: 40
- `critical_threshold_percent`: 30

**Confidence level**:
- utilization 40-50%: MEDIUM (60%)
- utilization 30-40%: HIGH (80%)
- utilization <30%: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_consumption_over_allocated_memory",
  "function_app_name": "func-data-processor",
  "function_name": "ProcessDataFunction",
  "hosting_plan_sku": {
    "tier": "Dynamic"
  },
  "monitoring_period_days": 30,
  "total_invocations": 100000,
  "configured_memory_mb": 1536,
  "avg_memory_used_mb": 600,
  "memory_utilization_percent": 39,
  "avg_duration_seconds": 2,
  "current_monthly_gb_seconds": 300000,
  "current_monthly_cost": 4.80,
  "recommended_memory_mb": 900,
  "optimized_monthly_gb_seconds": 180000,
  "optimized_monthly_cost": 2.88,
  "monthly_savings_potential": 1.92,
  "annual_savings_potential": 23.04,
  "recommendation": "Reduce memory allocation from 1536 MB to 900 MB",
  "confidence_level": "HIGH"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 4. `functions_always_on_consumption` - Always On configuré sur Consumption plan

**Détection**: Always On = true sur Consumption plan (feature non supportée/ignorée).

**Logique**:
```python
# Consumption plan
if hosting_plan.sku.tier == 'Dynamic':
    # Récupérer configuration Always On
    site_config = web_client.web_apps.get_configuration(
        resource_group_name=rg_name,
        name=function_app.name
    )

    # Vérifier Always On
    if site_config.always_on:
        # Always On activé sur Consumption = configuration invalide
        # Feature ignorée mais peut créer confusion

        flag_as_wasteful(function_app, severity="LOW")
```

**Calcul coût**:
```python
# Always On sur Consumption plan = AUCUN coût
# (feature simplement ignorée par Azure)

# Mais recommandation de cleanup pour:
# 1. Éviter confusion
# 2. Clarifier que Consumption n'a pas Always On
# 3. Si besoin Always On → migrer vers Premium

monthly_cost_impact = 0  # Pas de coût direct

# Si devait migrer vers Premium pour Always On:
# premium_cost = $388/mois
# consumption_cost = variable (depends on usage)

# Recommandation: Désactiver Always On ou migrer Premium si vraiment besoin
```

**Paramètres configurables**:
- `min_age_days`: 7 (défaut)
- `severity`: "LOW" (pas de coût direct)

**Confidence level**:
- Toujours LOW (40%) - Configuration invalide mais pas de coût

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_always_on_consumption",
  "function_app_name": "func-api-consumption",
  "hosting_plan_sku": {
    "tier": "Dynamic"
  },
  "always_on_configured": true,
  "always_on_effective": false,
  "monthly_cost_impact": 0,
  "recommendation": "Disable Always On (not supported on Consumption) or migrate to Premium",
  "note": "Always On is ignored on Consumption plan",
  "confidence_level": "LOW"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 5. `functions_premium_plan_oversized` - Premium Plan surdimensionné

**Détection**: Premium EP3 (4 vCPU) avec CPU utilization <20%.

**Logique**:
```python
# Premium plan
if 'ElasticPremium' in hosting_plan.sku.tier:
    sku_name = hosting_plan.sku.name  # EP1, EP2, EP3

    # Query CPU utilization via Azure Monitor
    avg_cpu_percent = query_avg_cpu_utilization(
        function_app,
        timedelta(days=30)
    )

    # Si <20% CPU
    if avg_cpu_percent < cpu_threshold:
        # Plan surdimensionné

        # Recommander downgrade
        current_sku = sku_name
        recommended_sku = recommend_premium_downgrade(current_sku, avg_cpu_percent)

        flag_as_wasteful(function_app, current_sku, recommended_sku)
```

**Calcul coût**:
```python
# Coût actuel (EP3)
current_sku = "EP3"
current_hourly_cost = 2.128  # $/heure
current_monthly_cost = current_hourly_cost * 730  # $1,553/mois

# Utilization: 15% CPU
avg_cpu_percent = 15

# SKU recommandé: EP1 (1 vCPU au lieu de 4 vCPU)
recommended_sku = "EP1"
recommended_hourly_cost = 0.532
recommended_monthly_cost = recommended_hourly_cost * 730  # $388/mois

# Économie potentielle
monthly_savings = current_monthly_cost - recommended_monthly_cost  # $1,165/mois (75%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Premium Plan Downgrade Matrix**:
```python
downgrade_recommendations = {
    # Si avg_cpu <15%
    ("EP3", 15): "EP1",   # 4 vCPU → 1 vCPU (économie $1,165/mois, 75%)
    ("EP2", 15): "EP1",   # 2 vCPU → 1 vCPU (économie $388/mois, 50%)

    # Si avg_cpu 15-20%
    ("EP3", 20): "EP2",   # 4 vCPU → 2 vCPU (économie $777/mois, 50%)
}
```

**Paramètres configurables**:
- `monitoring_period_days`: 30 (défaut)
- `cpu_threshold`: 20 (%)
- `alert_threshold_percent`: 25
- `critical_threshold_percent`: 15

**Confidence level**:
- avg_cpu% 20-25%: MEDIUM (60%)
- avg_cpu% 15-20%: HIGH (80%)
- avg_cpu% <15%: CRITICAL (95%)

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_premium_plan_oversized",
  "function_app_name": "func-heavy-workload",
  "hosting_plan_name": "ASP-premium-ep3",
  "current_sku": {
    "name": "EP3",
    "tier": "ElasticPremium",
    "vcpus": 4,
    "memory_gb": 14
  },
  "monitoring_period_days": 30,
  "avg_cpu_percent": 14.8,
  "max_cpu_percent": 35.2,
  "p95_cpu_percent": 28.1,
  "current_monthly_cost": 1553.00,
  "recommended_sku": {
    "name": "EP1",
    "vcpus": 1,
    "memory_gb": 3.5
  },
  "recommended_monthly_cost": 388.00,
  "monthly_savings_potential": 1165.00,
  "annual_savings_potential": 13980.00,
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 6. `functions_dev_test_premium` - Premium Plan pour environnements dev/test

**Détection**: Function App avec tags dev/test sur Premium plan.

**Logique**:
```python
# Identifier environnement dev/test
tags = function_app.tags or {}

is_dev_test = (
    tags.get('environment', '').lower() in ['dev', 'test', 'development', 'testing', 'staging'] or
    'dev' in function_app.name.lower() or
    'test' in function_app.name.lower()
)

# Premium plan
if is_dev_test and 'ElasticPremium' in hosting_plan.sku.tier:
    # Premium wasteful pour dev/test
    # Consumption plan plus adapté (scale to zero)

    flag_as_wasteful(function_app)
```

**Calcul coût**:
```python
# Premium plan actuel (EP1)
premium_monthly_cost = 388  # $/mois (toujours actif)

# Consumption plan alternatif
# Supposons usage dev/test: 500 invocations/mois
invocations = 500
avg_memory_gb = 0.512
avg_duration_sec = 1

# Consumption cost
gb_seconds = invocations * avg_memory_gb * avg_duration_sec  # 256 GB-s
consumption_cost = gb_seconds * 0.000016  # $0.004/mois (FREE GRANT)

# Économie potentielle
monthly_savings = premium_monthly_cost - consumption_cost  # $388/mois (99.9%)

already_wasted = monthly_savings * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `dev_test_tags`: ['dev', 'test', 'development', 'testing', 'staging']
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (40%) - Nouveau environnement
- 30-60 jours: MEDIUM (70%) - Probablement wasteful
- 60-90 jours: HIGH (85%) - Définitivement wasteful
- >90 jours: CRITICAL (95%) - Waste confirmé

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_dev_test_premium",
  "function_app_name": "func-dev-testing",
  "environment_tag": "dev",
  "tags": {"environment": "development", "team": "platform"},
  "hosting_plan_sku": {
    "name": "EP1",
    "tier": "ElasticPremium"
  },
  "created_date": "2024-06-01T10:00:00Z",
  "age_days": 210,
  "avg_monthly_invocations": 450,
  "current_monthly_cost": 388.00,
  "consumption_equivalent_cost": 0.003,
  "monthly_savings_potential": 387.99,
  "annual_savings_potential": 4655.88,
  "recommendation": "Migrate to Consumption plan for dev/test workloads",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

#### 7. `functions_multiple_plans_same_app` - Plusieurs App Service Plans pour même application

**Détection**: Plusieurs Premium plans pour functions de même application.

**Logique**:
```python
# Grouper Function Apps par application (via tags ou naming convention)
function_apps_by_app = {}

for function_app in all_function_apps:
    app_name = get_application_name(function_app)  # ex: via tag "application"

    if app_name not in function_apps_by_app:
        function_apps_by_app[app_name] = []

    function_apps_by_app[app_name].append(function_app)

# Pour chaque application
for app_name, function_apps in function_apps_by_app.items():
    # Compter App Service Plans distincts
    unique_plans = set()

    for func_app in function_apps:
        plan_id = func_app.server_farm_id
        unique_plans.add(plan_id)

    # Si >1 plan pour même application
    if len(unique_plans) > 1:
        # Redondance de plans = waste

        # Recommander consolidation
        flag_as_wasteful(app_name, len(unique_plans))
```

**Calcul coût**:
```python
# Exemple: 3 Premium EP1 plans pour même application
plan_count = 3
cost_per_plan = 388  # $/mois

# Coût actuel
current_monthly_cost = plan_count * cost_per_plan  # $1,164/mois

# Coût optimisé (1 plan consolidé)
optimized_plan_count = 1
optimized_monthly_cost = optimized_plan_count * cost_per_plan  # $388/mois

# Économie potentielle
monthly_savings = current_monthly_cost - optimized_monthly_cost  # $776/mois (67%)

already_wasted = monthly_savings * (age_days / 30)
```

**Paramètres configurables**:
- `min_age_days`: 30 (défaut)
- `max_plans_per_app`: 1 (défaut)
- `alert_threshold_days`: 60
- `critical_threshold_days`: 90

**Confidence level**:
- age_days < 30: LOW (35%) - Peut être migration en cours
- 30-60 jours: MEDIUM (65%) - Probablement redondant
- 60-90 jours: HIGH (80%) - Redondance confirmée
- >90 jours: CRITICAL (90%) - Waste confirmé

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_multiple_plans_same_app",
  "application_name": "ecommerce-api",
  "function_apps": [
    {
      "name": "func-orders-api",
      "hosting_plan_id": "/subscriptions/.../asp-premium-1"
    },
    {
      "name": "func-payments-api",
      "hosting_plan_id": "/subscriptions/.../asp-premium-2"
    },
    {
      "name": "func-inventory-api",
      "hosting_plan_id": "/subscriptions/.../asp-premium-3"
    }
  ],
  "unique_plan_count": 3,
  "plan_sku": "EP1",
  "current_monthly_cost": 1164.00,
  "optimized_plan_count": 1,
  "optimized_monthly_cost": 388.00,
  "monthly_savings_potential": 776.00,
  "annual_savings_potential": 9312.00,
  "recommendation": "Consolidate functions into single App Service Plan",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

## Phase 2 - Azure Monitor Métriques (3 scénarios)

### 8. `functions_low_invocation_rate_premium` - Premium avec <1000 invocations/mois

**Détection**: Premium plan avec très faible taux d'invocations via Application Insights.

**Logique**:
```python
# Premium plan
if 'ElasticPremium' in hosting_plan.sku.tier:
    # Query Application Insights
    app_insights_key = get_app_insights_key(function_app)

    # Query invocations (requests count)
    query = """
    requests
    | where timestamp > ago(30d)
    | summarize count()
    """

    result = query_application_insights(app_insights_key, query)
    total_invocations = result[0]['count_']

    # Threshold: 1000 invocations/mois
    if total_invocations < low_invocation_threshold:
        # Premium wasteful

        # Calculer coût vs Consumption
        premium_cost = calculate_premium_monthly_cost(hosting_plan)
        consumption_cost = estimate_consumption_cost(total_invocations)

        monthly_savings = premium_cost - consumption_cost

        flag_as_wasteful(function_app, monthly_savings)
```

**Calcul coût**:
```python
# Premium EP1
premium_monthly_cost = 388  # $/mois

# Invocations: 800/mois
invocations = 800
avg_memory_gb = 0.512
avg_duration_sec = 1.5

# Consumption cost
# Executions
exec_cost = (invocations / 1_000_000) * 0.20  # $0.00016

# GB-seconds
gb_seconds = invocations * avg_memory_gb * avg_duration_sec  # 614.4 GB-s
gb_seconds_cost = gb_seconds * 0.000016  # $0.0098

# Total Consumption
consumption_cost = exec_cost + gb_seconds_cost  # $0.0099 (FREE GRANT)

# Économie
monthly_savings = premium_monthly_cost - consumption_cost  # $388/mois (99.97%)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `low_invocation_threshold`: 1000 (invocations/mois)
- `monitoring_period_days`: 30 (défaut)
- `alert_threshold_invocations`: 5000
- `critical_threshold_invocations`: 1000

**Confidence level**:
- invocations 1000-5000: MEDIUM (65%)
- invocations 500-1000: HIGH (85%)
- invocations <500: CRITICAL (98%)

**Application Insights Query**:
```python
from azure.applicationinsights.query import ApplicationInsightsDataClient
from datetime import datetime, timedelta

# Initialize client
app_insights_client = ApplicationInsightsDataClient(credential)

# Query invocations
query = """
requests
| where timestamp > ago(30d)
| summarize
    TotalInvocations = count(),
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95)
by bin(timestamp, 1d)
"""

result = app_insights_client.query(
    app_id=app_insights_id,
    query=query
)

# Parse results
total_invocations = sum(row['TotalInvocations'] for row in result.tables[0].rows)
avg_duration_ms = sum(row['AvgDuration'] for row in result.tables[0].rows) / len(result.tables[0].rows)

print(f"Total invocations (30 days): {total_invocations}")
print(f"Avg duration: {avg_duration_ms:.2f} ms")
```

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_low_invocation_rate_premium",
  "function_app_name": "func-scheduled-job",
  "hosting_plan_sku": {
    "name": "EP1",
    "tier": "ElasticPremium"
  },
  "monitoring_period_days": 30,
  "total_invocations": 750,
  "avg_invocations_per_day": 25,
  "avg_duration_ms": 1200,
  "avg_memory_mb": 512,
  "current_monthly_cost": 388.00,
  "consumption_equivalent_cost": 0.009,
  "monthly_savings_potential": 387.99,
  "annual_savings_potential": 4655.88,
  "recommendation": "Migrate to Consumption plan - very low usage",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

### 9. `functions_high_error_rate` - Taux d'erreur >50%

**Détection**: Function avec taux d'erreurs >50% via Application Insights.

**Logique**:
```python
# Query Application Insights pour erreurs
query = """
requests
| where timestamp > ago(30d)
| summarize
    TotalRequests = count(),
    FailedRequests = countif(success == false)
| extend ErrorRate = (FailedRequests * 100.0) / TotalRequests
"""

result = query_application_insights(app_insights_key, query)
error_rate_percent = result[0]['ErrorRate']

# Si >50% erreurs
if error_rate_percent > high_error_rate_threshold:
    # Executions wasteful (erreurs consomment resources)

    total_requests = result[0]['TotalRequests']
    failed_requests = result[0]['FailedRequests']

    # Calculer coût des erreurs
    cost_of_errors = calculate_execution_cost(failed_requests)

    flag_as_wasteful(function_app, error_rate_percent, cost_of_errors)
```

**Calcul coût**:
```python
# Total invocations: 100,000/mois
total_invocations = 100_000

# Error rate: 60%
error_rate_percent = 60
failed_invocations = total_invocations * (error_rate_percent / 100)  # 60,000

# Coût des erreurs (Consumption plan)
avg_memory_gb = 0.512
avg_duration_sec = 0.5  # Erreurs souvent plus rapides

# Executions cost (erreurs)
error_exec_cost = (failed_invocations / 1_000_000) * 0.20  # $0.012

# GB-seconds cost (erreurs)
error_gb_seconds = failed_invocations * avg_memory_gb * avg_duration_sec  # 15,360 GB-s
error_gb_seconds_cost = error_gb_seconds * 0.000016  # $0.246

# Total coût wasteful (erreurs)
monthly_waste = error_exec_cost + error_gb_seconds_cost  # $0.258/mois

# Si Premium plan: Waste encore plus élevé (instances toujours actives)
# Premium EP1: $388/mois dont 60% wasted = $232.80/mois

# Économie potentielle si erreurs fixées
monthly_savings = monthly_waste  # Minimum $0.26/mois (Consumption)
# Ou $232.80/mois (Premium)

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `high_error_rate_threshold`: 50 (%)
- `monitoring_period_days`: 30 (défaut)
- `alert_threshold_percent`: 30
- `critical_threshold_percent`: 50

**Confidence level**:
- error_rate 50-70%: HIGH (85%) - Problème sérieux
- error_rate >70%: CRITICAL (98%) - Critique

**Application Insights Query**:
```python
# Query erreurs détaillées
query = """
requests
| where timestamp > ago(30d)
| where success == false
| summarize
    ErrorCount = count(),
    SampleErrors = take_any(resultCode, 3)
by operation_Name
| order by ErrorCount desc
"""

result = app_insights_client.query(app_id, query)

# Analyser top erreurs
for row in result.tables[0].rows:
    function_name = row['operation_Name']
    error_count = row['ErrorCount']
    sample_codes = row['SampleErrors']

    print(f"{function_name}: {error_count} errors (codes: {sample_codes})")
```

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_high_error_rate",
  "function_app_name": "func-external-api",
  "hosting_plan_sku": {
    "tier": "Dynamic"
  },
  "monitoring_period_days": 30,
  "total_invocations": 100000,
  "failed_invocations": 60000,
  "error_rate_percent": 60,
  "top_error_codes": ["500", "502", "timeout"],
  "monthly_waste_consumption": 0.26,
  "recommendation": "Fix errors to reduce wasteful executions",
  "debugging_tip": "Check Application Insights exceptions for root cause",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

### 10. `functions_long_execution_time` - Temps d'exécution excessif

**Détection**: Durée moyenne d'exécution >5 minutes via Application Insights.

**Logique**:
```python
# Query Application Insights pour durée
query = """
requests
| where timestamp > ago(30d)
| summarize
    AvgDuration = avg(duration),
    P95Duration = percentile(duration, 95),
    MaxDuration = max(duration),
    TotalRequests = count()
"""

result = query_application_insights(app_insights_key, query)
avg_duration_ms = result[0]['AvgDuration']
avg_duration_min = avg_duration_ms / 60000

# Si >5 minutes moyenne
if avg_duration_min > long_execution_threshold:
    # Execution time excessive = coût élevé

    total_requests = result[0]['TotalRequests']

    # Calculer waste vs optimized duration
    optimized_duration_min = 0.5  # Target: 30 seconds

    cost_current = calculate_execution_cost(
        total_requests,
        avg_duration_min
    )

    cost_optimized = calculate_execution_cost(
        total_requests,
        optimized_duration_min
    )

    monthly_savings = cost_current - cost_optimized

    flag_as_wasteful(function_app, avg_duration_min, monthly_savings)
```

**Calcul coût**:
```python
# Invocations: 10,000/mois
invocations = 10_000

# Durée actuelle: 8 minutes moyenne
avg_duration_min = 8
avg_duration_sec = avg_duration_min * 60  # 480 seconds

# Memory: 1 GB
avg_memory_gb = 1.0

# GB-seconds actuel
gb_seconds_current = invocations * avg_memory_gb * avg_duration_sec  # 4,800,000 GB-s
cost_current = gb_seconds_current * 0.000016  # $76.80/mois

# Durée optimisée: 30 seconds (16x improvement)
optimized_duration_sec = 30

# GB-seconds optimisé
gb_seconds_optimized = invocations * avg_memory_gb * optimized_duration_sec  # 300,000 GB-s
cost_optimized = gb_seconds_optimized * 0.000016  # $4.80/mois

# Économie potentielle
monthly_savings = cost_current - cost_optimized  # $72/mois (94%)

# À grande échelle (100K invocations/mois)
# Économie: $720/mois

already_wasted = monthly_savings * (monitoring_period_days / 30)
```

**Paramètres configurables**:
- `long_execution_threshold`: 5 (minutes)
- `monitoring_period_days`: 30 (défaut)
- `alert_threshold_minutes`: 3
- `critical_threshold_minutes`: 5

**Confidence level**:
- avg_duration 3-5 min: MEDIUM (65%) - Peut être optimisé
- avg_duration 5-10 min: HIGH (85%) - Clairement inefficient
- avg_duration >10 min: CRITICAL (98%) - Très wasteful

**Application Insights Query**:
```python
# Query duration analysis
query = """
requests
| where timestamp > ago(30d)
| summarize
    AvgDuration = avg(duration),
    P50Duration = percentile(duration, 50),
    P95Duration = percentile(duration, 95),
    P99Duration = percentile(duration, 99),
    MaxDuration = max(duration),
    SlowRequests = countif(duration > 300000)  // >5 min
by operation_Name
| order by AvgDuration desc
"""

result = app_insights_client.query(app_id, query)

# Analyser fonctions lentes
for row in result.tables[0].rows:
    function_name = row['operation_Name']
    avg_duration_ms = row['AvgDuration']
    slow_count = row['SlowRequests']

    print(f"{function_name}: avg {avg_duration_ms/1000:.2f}s ({slow_count} slow requests)")
```

**Metadata JSON attendu**:
```json
{
  "resource_type": "azure_function_app",
  "scenario": "functions_long_execution_time",
  "function_app_name": "func-batch-processor",
  "function_name": "ProcessLargeBatch",
  "hosting_plan_sku": {
    "tier": "Dynamic"
  },
  "monitoring_period_days": 30,
  "total_invocations": 10000,
  "avg_duration_seconds": 480,
  "p95_duration_seconds": 720,
  "max_duration_seconds": 1200,
  "avg_memory_gb": 1.0,
  "current_monthly_gb_seconds": 4800000,
  "current_monthly_cost": 76.80,
  "optimized_duration_seconds": 30,
  "optimized_monthly_cost": 4.80,
  "monthly_savings_potential": 72.00,
  "annual_savings_potential": 864.00,
  "recommendation": "Optimize code to reduce execution time (async I/O, caching, batching)",
  "confidence_level": "CRITICAL"
}
```

**Fichier**: `backend/app/providers/azure.py` (nouveau à implémenter)

---

## 🧪 Matrice de Test

| # | Scénario | Phase | Implémenté | Testé | Priorité | Impact ROI |
|---|----------|-------|-----------|-------|----------|------------|
| 1 | `functions_never_invoked` | 1 | ⚠️ | ❌ | **P1** | 🔥 Medium-High ($0-388/mois) |
| 2 | `functions_premium_plan_idle` | 1 | ⚠️ | ❌ | **P0** | 🔥🔥🔥 Critical ($388/mois, 50% fréquence) |
| 3 | `functions_consumption_over_allocated_memory` | 1 | ❌ | ❌ | **P2** | 💰 Low ($2-20/mois) |
| 4 | `functions_always_on_consumption` | 1 | ❌ | ❌ | **P3** | 💰 None (config cleanup) |
| 5 | `functions_premium_plan_oversized` | 1 | ❌ | ❌ | **P0** | 🔥🔥🔥 Critical ($1,165/mois, 20% fréquence) |
| 6 | `functions_dev_test_premium` | 1 | ❌ | ❌ | **P0** | 🔥🔥 High ($388/mois, 25% fréquence) |
| 7 | `functions_multiple_plans_same_app` | 1 | ❌ | ❌ | **P1** | 🔥🔥 High ($776/mois, 10% fréquence) |
| 8 | `functions_low_invocation_rate_premium` | 2 | ❌ | ❌ | **P0** | 🔥🔥🔥 Critical ($388/mois, 40% fréquence) |
| 9 | `functions_high_error_rate` | 2 | ❌ | ❌ | **P2** | 💰 Low-Medium ($0.26-233/mois) |
| 10 | `functions_long_execution_time` | 2 | ❌ | ❌ | **P1** | 🔥 Medium ($72/mois, 15% fréquence) |

**Légende**:
- ✅ Implémenté
- ⚠️ Stub existant (besoin finalisation)
- ❌ Non implémenté
- **P0**: Critique (Quick Win)
- **P1**: Haute priorité
- **P2**: Moyenne priorité
- **P3**: Basse priorité (cleanup)

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

# Installer Azure Functions Core Tools
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

---

### Test Scénario #1: `functions_never_invoked`

**Objectif**: Créer Function App sans jamais l'invoquer.

```bash
# Variables
LOCATION="eastus"
RG_NAME="rg-cloudwaste-test-functions"
STORAGE_NAME="stfunctest$(date +%s)"
FUNC_APP_NAME="func-never-invoked-$(date +%s)"
PLAN_NAME="asp-premium-test"

# Créer resource group
az group create --name $RG_NAME --location $LOCATION

# Créer storage account (requis pour Functions)
az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RG_NAME \
  --location $LOCATION \
  --sku Standard_LRS

# Créer Premium plan
az functionapp plan create \
  --resource-group $RG_NAME \
  --name $PLAN_NAME \
  --location $LOCATION \
  --sku EP1 \
  --is-linux

# Créer Function App (Python)
az functionapp create \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --storage-account $STORAGE_NAME \
  --plan $PLAN_NAME \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4

# Vérifier création (mais ne jamais déployer ni invoquer)
az functionapp show \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --query "{name:name, state:state, kind:kind, hostingPlan:serverFarmId}" \
  --output json

# Expected: Function App créée mais 0 functions déployées, 0 invocations
# Coût: $388/mois (Premium EP1) wasteful

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

**Résultat attendu**:
```json
{
  "name": "func-never-invoked-1706453200",
  "state": "Running",
  "kind": "functionapp,linux",
  "hostingPlan": "/subscriptions/.../asp-premium-test"
}
```

---

### Test Scénario #2: `functions_premium_plan_idle`

**Objectif**: Function App Premium avec très peu d'invocations.

```bash
# Créer Function App Premium (reprendre étapes test #1)
# ... (omis pour brevity)

# Déployer une simple function
mkdir -p ~/func-test && cd ~/func-test

# Initialiser Functions project
func init --python

# Créer HTTP trigger function
func new --name HttpTrigger --template "HTTP trigger" --authlevel anonymous

# Déployer
func azure functionapp publish $FUNC_APP_NAME

# Invoquer seulement 5 fois (très bas)
for i in {1..5}; do
  curl "https://${FUNC_APP_NAME}.azurewebsites.net/api/HttpTrigger?name=Test"
  sleep 1
done

# Attendre quelques heures pour métriques
sleep 3600

# Query invocations via Application Insights (si configuré)
# Ou vérifier via Portal: Function App > Monitor > Invocations

# Expected: 5 invocations total
# Coût: $388/mois (Premium EP1)
# Alternative Consumption: $0 (free grant)
# Économie: $388/mois (99.9%)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #3: `functions_consumption_over_allocated_memory`

**Objectif**: Function avec memory surdimensionnée.

```bash
# Créer Function App Consumption
RG_NAME="rg-cloudwaste-test-functions"
STORAGE_NAME="stfunccons$(date +%s)"
FUNC_APP_NAME="func-over-memory-$(date +%s)"

az group create --name $RG_NAME --location eastus --output none

az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RG_NAME \
  --location eastus \
  --sku Standard_LRS --output none

# Créer Function App Consumption (pas de plan, dynamic)
az functionapp create \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --storage-account $STORAGE_NAME \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4

# Déployer function avec memory élevée
cd ~/func-test

# Modifier host.json pour augmenter memory
cat > host.json <<'EOF'
{
  "version": "2.0",
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  },
  "functionTimeout": "00:10:00"
}
EOF

# Note: Memory allocation sur Consumption = dynamique (jusqu'à 1.5 GB)
# Simuler via function qui n'utilise que peu de RAM

cat > HttpTrigger/__init__.py <<'EOF'
import logging
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger processed a request.')

    # Utilise très peu de RAM (quelques MB)
    result = "Hello, World!"

    return func.HttpResponse(result, status_code=200)
EOF

# Déployer
func azure functionapp publish $FUNC_APP_NAME

# Invoquer plusieurs fois
for i in {1..100}; do
  curl -s "https://${FUNC_APP_NAME}.azurewebsites.net/api/HttpTrigger" > /dev/null
done

# Via Application Insights (si configuré), vérifier:
# - Memory allocated: ~1.5 GB (max Consumption)
# - Memory used: <100 MB (real usage)
# - Waste: 93% memory over-allocated

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #5: `functions_premium_plan_oversized`

**Objectif**: Premium EP3 avec faible utilization CPU.

```bash
# Créer Function App Premium EP3
RG_NAME="rg-cloudwaste-test-functions"
STORAGE_NAME="stfuncep3$(date +%s)"
FUNC_APP_NAME="func-oversized-$(date +%s)"
PLAN_NAME="asp-premium-ep3"

az group create --name $RG_NAME --location eastus --output none

az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RG_NAME \
  --location eastus \
  --sku Standard_LRS --output none

# Créer Premium EP3 plan (4 vCPU)
az functionapp plan create \
  --resource-group $RG_NAME \
  --name $PLAN_NAME \
  --location eastus \
  --sku EP3 \
  --is-linux

# Créer Function App
az functionapp create \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --storage-account $STORAGE_NAME \
  --plan $PLAN_NAME \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4

# Déployer function légère (n'utilise qu'1 vCPU max)
cd ~/func-test
func azure functionapp publish $FUNC_APP_NAME

# Invoquer avec charge légère
for i in {1..100}; do
  curl -s "https://${FUNC_APP_NAME}.azurewebsites.net/api/HttpTrigger" > /dev/null &
done
wait

# Attendre métriques CPU (plusieurs heures)
sleep 7200

# Query CPU metrics
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
PLAN_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.Web/serverfarms/$PLAN_NAME"

az monitor metrics list \
  --resource $PLAN_ID \
  --metric CpuPercentage \
  --start-time $(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT5M \
  --aggregation Average \
  --output table

# Expected: Avg CPU <20%
# EP3 coût: $1,553/mois
# EP1 coût: $388/mois (suffisant)
# Économie: $1,165/mois (75%)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #6: `functions_dev_test_premium`

**Objectif**: Function App dev avec Premium plan.

```bash
# Créer Function App avec tag environment=dev
RG_NAME="rg-cloudwaste-test-functions"
STORAGE_NAME="stfuncdev$(date +%s)"
FUNC_APP_NAME="func-dev-premium-$(date +%s)"
PLAN_NAME="asp-dev-premium"

az group create --name $RG_NAME --location eastus --output none

az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RG_NAME \
  --location eastus \
  --sku Standard_LRS --output none

# Créer Premium plan
az functionapp plan create \
  --resource-group $RG_NAME \
  --name $PLAN_NAME \
  --location eastus \
  --sku EP1 \
  --is-linux \
  --tags environment=dev team=engineering

# Créer Function App
az functionapp create \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --storage-account $STORAGE_NAME \
  --plan $PLAN_NAME \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --tags environment=dev

# Vérifier tags
az functionapp show \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --query "{name:name, tags:tags, planSku:'{hosting_plan_sku}'}" \
  --output json

# Expected: tags.environment = "dev" + Premium EP1
# Coût: $388/mois
# Recommandation: Migrer vers Consumption ($0 idle pour dev)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #8: `functions_low_invocation_rate_premium` (Application Insights)

**Objectif**: Query invocations via Application Insights.

```bash
# Prérequis: Function App avec Application Insights configuré
# ... (créer comme tests précédents)

# Activer Application Insights
APPINSIGHTS_NAME="ai-func-test"

az monitor app-insights component create \
  --app $APPINSIGHTS_NAME \
  --location eastus \
  --resource-group $RG_NAME

# Récupérer instrumentation key
APPINSIGHTS_KEY=$(az monitor app-insights component show \
  --app $APPINSIGHTS_NAME \
  --resource-group $RG_NAME \
  --query instrumentationKey \
  --output tsv)

# Configurer Function App
az functionapp config appsettings set \
  --name $FUNC_APP_NAME \
  --resource-group $RG_NAME \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=$APPINSIGHTS_KEY"

# Invoquer fonction plusieurs fois (faible volume)
for i in {1..50}; do
  curl -s "https://${FUNC_APP_NAME}.azurewebsites.net/api/HttpTrigger" > /dev/null
done

# Attendre métriques (10-15 min)
sleep 900

# Query via Application Insights Analytics (REST API ou Portal)
# Exemple query KQL:
# requests
# | where timestamp > ago(30d)
# | summarize count()

# Via CLI (nécessite app-insights extension):
az monitor app-insights query \
  --app $APPINSIGHTS_NAME \
  --resource-group $RG_NAME \
  --analytics-query "requests | where timestamp > ago(1h) | summarize count()" \
  --output table

# Expected: ~50 invocations (très bas pour Premium)
# Premium EP1: $388/mois
# Consumption equivalent: $0 (free grant)
# Économie: $388/mois

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

### Test Scénario #10: `functions_long_execution_time`

**Objectif**: Function avec durée d'exécution longue.

```bash
# Créer function avec sleep (simuler long processing)
cd ~/func-test

cat > LongRunningFunction/__init__.py <<'EOF'
import logging
import time
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Long running function started.')

    # Simuler traitement long (5 minutes)
    time.sleep(300)

    logging.info('Long running function completed.')
    return func.HttpResponse("Done after 5 minutes", status_code=200)
EOF

# Ajouter nouvelle function
func new --name LongRunningFunction --template "HTTP trigger" --authlevel anonymous

# Déployer
func azure functionapp publish $FUNC_APP_NAME

# Invoquer (attention: timeout 230 sec par défaut HTTP)
# Augmenter timeout d'abord
az functionapp config set \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --linux-fx-version "PYTHON|3.11"

# Modifier host.json pour timeout plus long
# (nécessite redéploiement avec host.json modifié)

# Invoquer en async (non-HTTP trigger mieux)
curl -X POST "https://${FUNC_APP_NAME}.azurewebsites.net/api/LongRunningFunction" &

# Attendre completion + métriques
sleep 400

# Query duration via Application Insights
az monitor app-insights query \
  --app $APPINSIGHTS_NAME \
  --resource-group $RG_NAME \
  --analytics-query "requests | where operation_Name == 'LongRunningFunction' | summarize avg(duration)" \
  --output table

# Expected: Avg duration ~300,000 ms (5 min)
# Coût (Consumption, 1 GB memory):
# 1 invocation × 1 GB × 300 sec = 300 GB-s
# Coût: 300 × $0.000016 = $0.0048
# Si optimisé à 30 sec: $0.00048 (90% économie)

# Cleanup
az group delete --name $RG_NAME --yes --no-wait
```

---

## 🔧 Troubleshooting Guide

### Problème 1: Function App ne peut pas basculer de Premium à Consumption

**Symptôme**: Erreur lors de la migration de plan.

**Cause**: Certaines features Premium incompatibles avec Consumption (VNET integration, Always On, etc.).

**Solution**:
```bash
# Vérifier configuration incompatible
az functionapp show \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --query "{alwaysOn:siteConfig.alwaysOn, vnetName:virtualNetworkSubnetId}" \
  --output json

# Désactiver Always On
az functionapp config set \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --always-on false

# Supprimer VNET integration si présent
az functionapp vnet-integration remove \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME

# Puis changer plan vers Consumption
# Note: Nécessite créer nouveau Consumption plan ou utiliser existant
az functionapp update \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --plan <consumption-plan-name>
```

---

### Problème 2: Application Insights métriques non disponibles

**Symptôme**: Invocations count = 0 dans queries.

**Cause**: Application Insights pas configuré ou délai propagation.

**Solution**:
```bash
# Vérifier Application Insights configuré
az functionapp config appsettings list \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --query "[?name=='APPINSIGHTS_INSTRUMENTATIONKEY'].value" \
  --output tsv

# Si vide, créer et configurer App Insights
APPINSIGHTS_NAME="ai-${FUNC_APP_NAME}"

az monitor app-insights component create \
  --app $APPINSIGHTS_NAME \
  --location eastus \
  --resource-group $RG_NAME \
  --application-type web

APPINSIGHTS_KEY=$(az monitor app-insights component show \
  --app $APPINSIGHTS_NAME \
  --resource-group $RG_NAME \
  --query instrumentationKey \
  --output tsv)

az functionapp config appsettings set \
  --name $FUNC_APP_NAME \
  --resource-group $RG_NAME \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=$APPINSIGHTS_KEY"

# Redémarrer function app
az functionapp restart \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME

# Attendre 10-15 min pour métriques
```

---

### Problème 3: Coût Consumption plus élevé que prévu

**Symptôme**: Facture Consumption supérieure à estimations.

**Diagnostic**:
```bash
# 1. Vérifier invocations totales
az monitor app-insights query \
  --app $APPINSIGHTS_NAME \
  --resource-group $RG_NAME \
  --analytics-query "requests | where timestamp > ago(30d) | summarize count()" \
  --output table

# 2. Vérifier durée moyenne
az monitor app-insights query \
  --app $APPINSIGHTS_NAME \
  --resource-group $RG_NAME \
  --analytics-query "requests | where timestamp > ago(30d) | summarize avg(duration)" \
  --output table

# 3. Vérifier memory usage (via custom metrics si configuré)
# Ou estimer via logs

# 4. Calculer GB-seconds
# invocations × memory_gb × duration_sec

# Exemple:
# 5M invocations × 1 GB × 2 sec = 10M GB-s
# Coût: 10M × $0.000016 = $160/mois (hors free grant)

# Optimisations possibles:
# - Réduire memory allocation
# - Optimiser code (reduce duration)
# - Caching pour réduire invocations
```

---

### Problème 4: Premium plan - Cold starts malgré Always On

**Symptôme**: Premières requêtes lentes même avec Premium.

**Cause**: Instances pas pré-warmed ou scale-in agressif.

**Solution**:
```bash
# Vérifier Always On activé
az functionapp config show \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --query "alwaysOn" \
  --output tsv

# Expected: true

# Vérifier minimum instances
az functionapp plan show \
  --resource-group $RG_NAME \
  --name $PLAN_NAME \
  --query "sku.capacity" \
  --output tsv

# Augmenter minimum instances (Premium)
az functionapp plan update \
  --resource-group $RG_NAME \
  --name $PLAN_NAME \
  --min-instances 2

# Configurer pre-warmed instances
az functionapp config appsettings set \
  --name $FUNC_APP_NAME \
  --resource-group $RG_NAME \
  --settings "WEBSITE_SWAP_WARMUP_PING_PATH=/api/warmup" \
               "WEBSITE_SWAP_WARMUP_PING_STATUSES=200"
```

---

### Problème 5: Memory limit exceeded (Consumption)

**Erreur**:
```
Function terminated due to memory limit exceeded
```

**Cause**: Function utilise >1.5 GB RAM (limite Consumption).

**Solution**:
```bash
# Option 1: Optimiser code pour réduire memory usage
# - Stream data instead of loading in memory
# - Process in batches
# - Use generators

# Option 2: Migrer vers Premium (plus de RAM)
# Premium EP1: 3.5 GB RAM
# Premium EP2: 7 GB RAM
# Premium EP3: 14 GB RAM

# Créer Premium plan
az functionapp plan create \
  --resource-group $RG_NAME \
  --name asp-premium-highmem \
  --location eastus \
  --sku EP2 \
  --is-linux

# Migrer function app
az functionapp update \
  --resource-group $RG_NAME \
  --name $FUNC_APP_NAME \
  --plan asp-premium-highmem

# Option 3: Refactorer en plusieurs functions (divide & conquer)
```

---

### Problème 6: Impossible de supprimer App Service Plan - Function Apps actives

**Erreur**:
```
Cannot delete plan because it has active function apps
```

**Cause**: Function Apps toujours associées au plan.

**Solution**:
```bash
# Lister function apps dans le plan
PLAN_ID="/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.Web/serverfarms/$PLAN_NAME"

az functionapp list \
  --query "[?serverFarmId=='$PLAN_ID'].name" \
  --output table

# Supprimer ou migrer chaque function app
for FUNC_APP in $(az functionapp list --query "[?serverFarmId=='$PLAN_ID'].name" -o tsv); do
  echo "Deleting $FUNC_APP..."
  az functionapp delete \
    --resource-group $RG_NAME \
    --name $FUNC_APP
done

# Puis supprimer plan
az functionapp plan delete \
  --resource-group $RG_NAME \
  --name $PLAN_NAME \
  --yes
```

---

## 💰 Impact Business & ROI

### Économies Potentielles par Scénario

| Scénario | Économie Mensuelle | Économie Annuelle | Fréquence* | ROI Annuel (20 Function Apps) |
|----------|-------------------|-------------------|------------|-------------------------------|
| `functions_never_invoked` | $0-388 | $0-4,656 | 10% | $931 |
| `functions_premium_plan_idle` | $388 | $4,656 | 50% | $46,560 |
| `functions_consumption_over_allocated` | $2-20 | $24-240 | 30% | $792 |
| `functions_always_on_consumption` | $0 | $0 | 5% | $0 |
| `functions_premium_plan_oversized` | $1,165 | $13,980 | 20% | $55,920 |
| `functions_dev_test_premium` | $388 | $4,656 | 25% | $23,280 |
| `functions_multiple_plans_same_app` | $776 | $9,312 | 10% | $18,624 |
| `functions_low_invocation_rate_premium` | $388 | $4,656 | 40% | $37,248 |
| `functions_high_error_rate` | $0.26-233 | $3-2,796 | 15% | $420 |
| `functions_long_execution_time` | $72 | $864 | 15% | $2,592 |
| **TOTAL** | | | | **$186,367/an** |

\* Fréquence = % des Function Apps affectées (estimé)

---

### Arguments Business

#### 1. **Premium vs Consumption: $388/mois vs $0 Idle**

**Stat clé**: Premium plan coûte **$388/mois minimum** (toujours 1 instance actif) vs Consumption **$0 idle**.

**Exemple décision**:
```
Question: Quand utiliser Premium vs Consumption?

Premium ($388/mois) si:
✅ >100,000 invocations/mois
✅ Need <1s cold start (latency-sensitive)
✅ Long-running functions (>5 min)
✅ VNET integration requise
✅ Predictable high load

Consumption ($0 idle) si:
✅ <100,000 invocations/mois
✅ Sporadic/unpredictable load
✅ Dev/test environments
✅ Background jobs (non latency-sensitive)
✅ Cost optimization prioritaire

Breakeven: ~100K-150K invocations/mois
```

**CloudWaste ROI**: 50% des Premium apps ont <10K invocations/mois → **$233,280/an** waste (20 apps)

#### 2. **50% des Premium Plans sont Idle ou Sous-Utilisés**

**Pattern courant**: Premium plan créé "par précaution", jamais revisité.

**Exemple réel**:
```
Function App "webhook-handler":
- Plan: Premium EP1 ($388/mois)
- Invocations: 75/mois (quasi idle)
- Coût par invocation: $388 / 75 = $5.17 per call!

Si migré vers Consumption:
- 75 invocations × 512 MB × 1s = 38.4 GB-s
- Coût: $0.0006/mois (FREE GRANT)

Économie: $388/mois = $4,656/an (99.98%)
```

**CloudWaste action**:
- Détecter Premium avec <1000 invocations/mois
- Recommander migration Consumption
- ROI: **$4,656/an par app** migrée

#### 3. **Premium Oversized: 75% Économie via Rightsizing**

**Problème**: Premium EP3 (4 vCPU) pour workload qui tient sur 1 vCPU.

**Cas d'usage**:
```
Function App "data-processor":
- Plan: Premium EP3 ($1,553/mois)
- CPU utilization: 15% moyenne
- Vraiment besoin: 1 vCPU (EP1)

Rightsizing EP3 → EP1:
- Coût actuel: $1,553/mois
- Coût optimisé: $388/mois
- Économie: $1,165/mois = $13,980/an (75%)
```

**CloudWaste action**:
- Query CPU/memory metrics via Azure Monitor
- Recommander downgrade si <20% CPU
- ROI: **$13,980/an par app** optimisée

#### 4. **Dev/Test sur Premium: Pure Waste**

**Problème**: Environnements dev/test sur Premium plan.

**Rationale incorrect**: "Dev doit ressembler à Prod (Premium)".

**Réalité**:
```
Dev/Test usage pattern:
- 8h/jour × 5j/semaine = 40h/semaine
- ~500 invocations/mois (tests manuels + CI/CD)

Premium EP1 (dev):
- Coût: $388/mois (24/7 actif)
- Utilization: <5%

Consumption (dev):
- Coût: $0/mois (free grant)
- Cold start: OK pour dev (non prod)

Économie: $388/mois = $4,656/an par environnement
```

**CloudWaste ROI**: 5 environnements dev/test × **$4,656/an** = **$23,280/an**

#### 5. **Long Execution Time: Code Optimization = 80-90% Savings**

**Problème**: Functions non optimisées consomment 10-20x plus de resources.

**Exemples optimizations**:
```
1. Async I/O (vs synchronous):
   - Avant: 10 sec (wait I/O)
   - Après: 0.5 sec (async)
   - Économie: 95%

2. Caching:
   - Avant: DB query each call (2 sec)
   - Après: Redis cache (0.1 sec)
   - Économie: 95%

3. Batching:
   - Avant: 1000 invocations × 100 items
   - Après: 100 invocations × 1000 items (batch)
   - Économie: 90%

4. Cold start optimization:
   - Lazy imports
   - Connection pooling
   - Global variables reuse
```

**Exemple calcul**:
```
Function "process-events":
- Invocations: 100K/mois
- Duration actuelle: 8 sec
- Memory: 1 GB

GB-seconds: 100K × 1 GB × 8 sec = 800K GB-s
Coût: 800K × $0.000016 = $12.80/mois

Après optimization (1 sec duration):
GB-seconds: 100K × 1 GB × 1 sec = 100K GB-s
Coût: 100K × $0.000016 = $1.60/mois

Économie: $11.20/mois = $134.40/an (87.5%)
```

**CloudWaste action**:
- Identifier functions >5 min duration
- Recommander optimizations (async, caching, batching)
- ROI: **$134-864/an par function** optimisée

---

### ROI Global Estimé

**Organisation moyenne (20 Function Apps)**:

| Catégorie | Apps Affectées | Économie/App | ROI Annuel |
|-----------|----------------|--------------|------------|
| Premium plan idle | 10 (50%) | $4,656 | $46,560 |
| Premium oversized | 4 (20%) | $13,980 | $55,920 |
| Low invocation Premium | 8 (40%) | $4,656 | $37,248 |
| Dev/test Premium | 5 (25%) | $4,656 | $23,280 |
| Multiple plans | 2 (10%) | $9,312 | $18,624 |
| Long execution time | 3 (15%) | $864 | $2,592 |
| **TOTAL** | | | **$184,224/an** |

**CloudWaste Pricing**: ~$5,000-8,000/an (20 apps)
**ROI Net**: **$176,224-179,224/an (2,203-2,240% ROI)**
**Payback Period**: **< 2 semaines**

---

## 📚 Références Officielles Azure

### Azure Functions

1. **Pricing**
   https://azure.microsoft.com/en-us/pricing/details/functions/

2. **Consumption Plan**
   https://learn.microsoft.com/en-us/azure/azure-functions/consumption-plan

3. **Premium Plan**
   https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan

4. **Dedicated (App Service) Plan**
   https://learn.microsoft.com/en-us/azure/azure-functions/dedicated-plan

5. **Flex Consumption Plan (2025)**
   https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan

6. **Scale and Hosting**
   https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale

7. **Best Practices**
   https://learn.microsoft.com/en-us/azure/azure-functions/functions-best-practices

8. **Performance and Reliability**
   https://learn.microsoft.com/en-us/azure/azure-functions/performance-reliability

### Cost Optimization

9. **Estimating Consumption Costs**
   https://learn.microsoft.com/en-us/azure/azure-functions/functions-consumption-costs

10. **Cost Optimization Guide**
    https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-azure-devops

### Monitoring & Application Insights

11. **Monitor Azure Functions**
    https://learn.microsoft.com/en-us/azure/azure-functions/functions-monitoring

12. **Application Insights Integration**
    https://learn.microsoft.com/en-us/azure/azure-functions/functions-monitoring

13. **Application Insights Query**
    https://learn.microsoft.com/en-us/azure/azure-monitor/logs/get-started-queries

14. **Metrics and Alerts**
    https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-use-azure-function-app-settings

### Azure SDK & Tools

15. **azure-mgmt-web (Python)**
    https://learn.microsoft.com/en-us/python/api/azure-mgmt-web/azure.mgmt.web

16. **azure-applicationinsights-query (Python)**
    https://pypi.org/project/azure-applicationinsights-query/

17. **Azure Functions Core Tools**
    https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local

18. **Azure CLI - Functions Commands**
    https://learn.microsoft.com/en-us/cli/azure/functionapp

### Performance Optimization

19. **Improve Performance**
    https://learn.microsoft.com/en-us/azure/azure-functions/performance-reliability

20. **Cold Start Optimization**
    https://learn.microsoft.com/en-us/azure/azure-functions/event-driven-scaling

21. **Connection Management**
    https://learn.microsoft.com/en-us/azure/azure-functions/manage-connections

### FinOps & Cost Management

22. **FinOps Best Practices**
    https://learn.microsoft.com/en-us/cloud-computing/finops/best-practices/

23. **Azure Cost Management**
    https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/cost-mgt-best-practices

24. **Azure Advisor Recommendations**
    https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations

---

## ✅ Checklist d'Implémentation

### Phase 1 - Scénarios Simples (Sprint 1)

- [ ] **Scénario #1**: `functions_never_invoked`
  - [ ] Compléter stub `scan_idle_lambda_functions()` (ligne 3073)
  - [ ] Query via `WebSiteManagementClient.web_apps.list()`
  - [ ] Filter: `kind.contains('functionapp')`
  - [ ] Query Application Insights total invocations
  - [ ] Tests

- [ ] **Scénario #2**: `functions_premium_plan_idle`
  - [ ] Fonction dans même stub
  - [ ] Filter Premium plans: `sku.tier == 'ElasticPremium'`
  - [ ] Query invocations last 30 days
  - [ ] Calculate savings vs Consumption
  - [ ] Tests

- [ ] **Scénario #3**: `functions_consumption_over_allocated_memory`
  - [ ] Fonction `scan_functions_memory_over_allocated()`
  - [ ] Query Application Insights memory usage
  - [ ] Compare configured vs actual
  - [ ] Rightsizing recommendations
  - [ ] Tests

- [ ] **Scénario #4**: `functions_always_on_consumption`
  - [ ] Fonction `scan_functions_always_on_consumption()`
  - [ ] Query site config `always_on`
  - [ ] Filter Consumption plans
  - [ ] Flag as config issue
  - [ ] Tests

- [ ] **Scénario #5**: `functions_premium_plan_oversized`
  - [ ] Fonction `scan_functions_premium_oversized()`
  - [ ] Query Azure Monitor CPU metrics
  - [ ] Calculate avg CPU%
  - [ ] Downgrade recommendations (EP3→EP1)
  - [ ] Tests

- [ ] **Scénario #6**: `functions_dev_test_premium`
  - [ ] Fonction `scan_functions_dev_test_premium()`
  - [ ] Detect dev/test tags
  - [ ] Filter Premium plans
  - [ ] Calculate savings vs Consumption
  - [ ] Tests

- [ ] **Scénario #7**: `functions_multiple_plans_same_app`
  - [ ] Fonction `scan_functions_multiple_plans()`
  - [ ] Group by application (tags or naming)
  - [ ] Count unique plans per app
  - [ ] Consolidation recommendations
  - [ ] Tests

### Phase 2 - Application Insights Métriques (Sprint 2)

- [ ] **Scénario #8**: `functions_low_invocation_rate_premium`
  - [ ] Fonction `scan_functions_low_invocations_premium()`
  - [ ] Query Application Insights `requests/count`
  - [ ] Filter Premium plans
  - [ ] Calculate breakeven vs Consumption
  - [ ] Tests

- [ ] **Scénario #9**: `functions_high_error_rate`
  - [ ] Fonction `scan_functions_high_error_rate()`
  - [ ] Query Application Insights `requests/failed`
  - [ ] Calculate error rate %
  - [ ] Estimate cost of errors
  - [ ] Tests

- [ ] **Scénario #10**: `functions_long_execution_time`
  - [ ] Fonction `scan_functions_long_execution()`
  - [ ] Query Application Insights `duration`
  - [ ] Calculate avg execution time
  - [ ] Optimization recommendations
  - [ ] Tests

### Infrastructure & Tests

- [ ] **Dependencies**
  - [ ] Add `azure-applicationinsights-query` to requirements.txt
  - [ ] Update `azure-mgmt-web` to latest
  - [ ] Add `azure-monitor-query` if not present

- [ ] **Database Schema**
  - [ ] Support Function App metadata (hosting_plan, sku, runtime)
  - [ ] Migration Alembic
  - [ ] Indexes

- [ ] **Detection Rules**
  - [ ] Règles par défaut Functions
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
  - [ ] Afficher Function Apps
  - [ ] Filtrer par plan type (Consumption/Premium/Dedicated)
  - [ ] Tri par coût, invocations

- [ ] **Resource Details**
  - [ ] Page détail Function App
  - [ ] Graphiques invocations, duration, errors
  - [ ] Actions (Migrate plan, Optimize)
  - [ ] Recommandations

- [ ] **Cost Calculator**
  - [ ] Estimateur économies Functions
  - [ ] Comparaison Consumption vs Premium
  - [ ] Simulation migration
  - [ ] Export PDF

---

## 🎯 Priorités d'Implémentation

### P0 - Quick Wins (Sprint 1)
1. `functions_premium_plan_idle` (**ROI critique** $388/mois, 50% fréquence)
2. `functions_premium_plan_oversized` (**ROI critique** $1,165/mois, 20% fréquence)
3. `functions_dev_test_premium` (économie $388/mois, 25% fréquence)
4. `functions_low_invocation_rate_premium` (**ROI critique** $388/mois, 40% fréquence)

**Raison**: Économie immédiate massive, haute fréquence, facile à détecter.

### P1 - High ROI (Sprint 2)
5. `functions_never_invoked` (économie $0-388/mois selon plan)
6. `functions_multiple_plans_same_app` (économie $776/mois)
7. `functions_long_execution_time` (économie $72/mois)

**Raison**: ROI élevé, fréquence moyenne.

### P2 - Optimization (Sprint 3)
8. `functions_consumption_over_allocated_memory` (économie $2-20/mois)
9. `functions_high_error_rate` (économie variable, quality improvement)

**Raison**: ROI faible-moyen mais améliore qualité.

### P3 - Cleanup (Sprint 4)
10. `functions_always_on_consumption` (économie $0, configuration cleanup)

**Raison**: Pas d'économie directe, cleanup seulement.

---

## 🚀 Quick Start

### Script Test Complet

```bash
#!/bin/bash
# Script: test-all-functions-scenarios.sh
# Description: Teste scénarios Azure Functions critiques

set -e

echo "🚀 CloudWaste - Test Azure Functions Scenarios"
echo "=============================================="

LOCATION="eastus"
BASE_RG="rg-cloudwaste-func-test"
STORAGE_BASE="stfunc$(date +%s)"

# Test #1: Premium Plan Idle
echo ""
echo "📊 Test #1: Premium Plan Idle"
RG_NAME="${BASE_RG}-idle"
STORAGE_NAME="${STORAGE_BASE}idle"
FUNC_APP_NAME="func-idle-$(date +%s)"
PLAN_NAME="asp-premium-idle"

az group create --name $RG_NAME --location $LOCATION --output none
az storage account create --name $STORAGE_NAME --resource-group $RG_NAME --location $LOCATION --sku Standard_LRS --output none
az functionapp plan create --resource-group $RG_NAME --name $PLAN_NAME --location $LOCATION --sku EP1 --is-linux --output none
az functionapp create --resource-group $RG_NAME --name $FUNC_APP_NAME --storage-account $STORAGE_NAME --plan $PLAN_NAME --runtime python --runtime-version 3.11 --functions-version 4 --output none

echo "✅ Premium EP1 created (idle, no invocations)"
echo "   Coût: \$388/mois wasteful"
az group delete --name $RG_NAME --yes --no-wait

# Test #2: Dev/Test Premium
echo ""
echo "📊 Test #2: Dev/Test on Premium Plan"
RG_NAME="${BASE_RG}-devtest"
STORAGE_NAME="${STORAGE_BASE}dev"
FUNC_APP_NAME="func-dev-$(date +%s)"
PLAN_NAME="asp-dev-premium"

az group create --name $RG_NAME --location $LOCATION --output none
az storage account create --name $STORAGE_NAME --resource-group $RG_NAME --location $LOCATION --sku Standard_LRS --output none
az functionapp plan create --resource-group $RG_NAME --name $PLAN_NAME --location $LOCATION --sku EP1 --is-linux --tags environment=dev --output none
az functionapp create --resource-group $RG_NAME --name $FUNC_APP_NAME --storage-account $STORAGE_NAME --plan $PLAN_NAME --runtime python --runtime-version 3.11 --functions-version 4 --tags environment=dev --output none

echo "✅ Dev environment on Premium EP1"
echo "   Coût: \$388/mois, should be Consumption (\$0 idle)"
az group delete --name $RG_NAME --yes --no-wait

echo ""
echo "✅ All tests completed!"
echo "   Total wasteful cost detected: ~\$776/mois"
echo "   Savings potential: \$776/mois (migrate to Consumption)"
echo "   Run CloudWaste scanner to detect these issues"
```

**Usage**:
```bash
chmod +x test-all-functions-scenarios.sh
./test-all-functions-scenarios.sh
```

---

## 📊 Résumé Exécutif

### Couverture

- **10 scénarios** (100% coverage)
- **7 Phase 1** (détection simple, configuration)
- **3 Phase 2** (Application Insights métriques)

### ROI Estimé

- **Économie moyenne**: $0-1,165/mois par Function App wasteful
- **ROI annuel**: **$184,224/an** (organisation 20 apps)
- **Payback period**: < **2 semaines**

### Insights Critiques 2025

- **Premium plan**: $388/mois minimum (toujours actif) vs **Consumption $0 idle**
- **50% des Premium plans idle** ou sous-utilisés
- **Breakeven**: ~100K-150K invocations/mois
- Premium utile si: >100K invocations + latency-sensitive
- Sinon: **Consumption = optimal**

### Next Steps

1. **Implémenter P0** (scénarios #2, #5, #6, #8) → Sprint 1
2. **Implémenter P1** (scénarios #1, #7, #10) → Sprint 2
3. **Implémenter P2-P3** (scénarios #3, #9, #4) → Sprint 3
4. **Tests end-to-end** + documentation utilisateur

---

**Dernière mise à jour**: 2025-01-28
**Auteur**: CloudWaste Documentation Team
**Version**: 1.0.0
