# Azure App Service (Web Apps) - Waste Detection Scenarios (100% Coverage)

## Table of Contents
1. [Introduction](#introduction)
2. [Phase 1 Scenarios - Simple Detection](#phase-1-scenarios---simple-detection)
3. [Phase 2 Scenarios - Metrics-Based Detection](#phase-2-scenarios---metrics-based-detection)
4. [Pricing Structure](#pricing-structure)
5. [Required Azure Permissions](#required-azure-permissions)
6. [Azure CLI Commands for Testing](#azure-cli-commands-for-testing)
7. [Comparison with Alternatives](#comparison-with-alternatives)
8. [Test Matrix](#test-matrix)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Business Impact Analysis](#business-impact-analysis)
11. [Implementation Roadmap](#implementation-roadmap)
12. [References](#references)

---

## Introduction

**Azure App Service** is a fully managed Platform-as-a-Service (PaaS) for hosting web applications, REST APIs, and mobile backends. It runs on **App Service Plans**, which are compute resource containers that can host multiple applications. This architecture creates unique waste patterns: an empty App Service Plan costs the same as a full one, and consolidation opportunities are common.

### Key Characteristics
- **App Service Plans**: Compute containers that host 1-N apps (pricing per plan, not per app)
- **Pricing Tiers**: Free, Shared, Basic (B1-B3), Standard (S1-S3), Premium v2/v3 (P1v2-P3v3), Isolated (I1v2-I3v2)
- **Auto-Scale**: Horizontal scaling (add instances) - available on Standard+ tiers only
- **Always On**: Keeps app loaded in memory (prevents cold starts, adds cost)
- **Deployment Slots**: Separate environments (staging, production) - each slot = additional instance cost

### Common Waste Patterns
1. **Empty App Service Plans** → Paying for compute with 0 apps → **100% waste**
2. **Premium tier in dev/test** → $146/month when $55 Basic would suffice → **62% waste**
3. **No auto-scale configured** → Fixed 3 instances when 1-3 needed → **50% waste**
4. **Always On for low-traffic apps** → 10-15% overhead for apps with <100 requests/day
5. **Multiple plans consolidation** → 3× S1 plans ($210) could be 1× S2 ($140) → **33% waste**

### Detection Strategy
- **Phase 1**: Configuration-based detection (plan SKU, app count, auto-scale config, Always On)
- **Phase 2**: Azure Monitor metrics (CPU, memory, HTTP requests, errors, response time)

---

## Phase 1 Scenarios - Simple Detection

### Scenario 1: Empty App Service Plan
**Detection Logic**: App Service Plan exists but has 0 applications deployed for >30 days.

```python
from azure.mgmt.web import WebSiteManagementClient
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

def detect_empty_app_service_plans(subscription_id: str) -> list:
    """
    Detect App Service Plans with no apps deployed.

    Returns: List of wasteful plans with cost impact
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_plans = []

    for plan in web_client.app_service_plans.list():
        # Count apps on this plan
        apps_on_plan = [
            app for app in web_client.web_apps.list()
            if app.server_farm_id == plan.id
        ]

        if len(apps_on_plan) == 0:
            # Check plan age
            if not plan.created_time:
                continue

            plan_age_days = (datetime.now(plan.created_time.tzinfo) - plan.created_time).days

            if plan_age_days < 7:
                continue  # Too new to judge

            # Calculate waste
            monthly_cost = calculate_plan_cost(plan.sku)

            confidence = 'medium'
            if plan_age_days >= 60:
                confidence = 'high'
            if plan_age_days >= 90:
                confidence = 'critical'

            wasteful_plans.append({
                'resource_id': plan.id,
                'name': plan.name,
                'resource_group': plan.id.split('/')[4],
                'location': plan.location,
                'sku_name': plan.sku.name,
                'sku_tier': plan.sku.tier,
                'plan_age_days': plan_age_days,
                'apps_count': 0,
                'estimated_monthly_cost': monthly_cost,
                'waste_percentage': 100,
                'confidence': confidence,
                'recommendation': 'Delete empty App Service Plan - no apps deployed',
                'scenario': 'app_service_plan_empty',
                'metadata': {
                    'created_date': plan.created_time.isoformat(),
                    'max_workers': plan.maximum_number_of_workers,
                    'current_workers': plan.number_of_workers
                }
            })

    return wasteful_plans

def calculate_plan_cost(sku) -> float:
    """Calculate monthly cost for App Service Plan."""
    # Pricing per month (East US, pay-as-you-go)
    sku_prices = {
        # Basic tier
        'B1': 13.14,
        'B2': 55.48,
        'B3': 104.03,
        # Standard tier
        'S1': 70.08,
        'S2': 140.16,
        'S3': 280.32,
        # Premium v2
        'P1v2': 146.00,
        'P2v2': 292.00,
        'P3v2': 584.00,
        # Premium v3
        'P0v3': 83.95,
        'P1v3': 219.00,
        'P2v3': 438.00,
        'P3v3': 876.00,
        # Isolated v2
        'I1v2': 438.00,
        'I2v2': 876.00,
        'I3v2': 1753.00,
        # Free/Shared
        'F1': 0.00,
        'D1': 9.49,
    }

    sku_name = sku.name
    base_cost = sku_prices.get(sku_name, 70.08)  # Default to S1

    # Multiply by current worker count (instances)
    capacity = sku.capacity if hasattr(sku, 'capacity') else 1
    total_cost = base_cost * capacity

    return round(total_cost, 2)
```

**Cost Impact**:
- Empty Basic B1: **$13/month** → 100% waste
- Empty Standard S1: **$70/month** → 100% waste
- Empty Premium P1v2: **$146/month** → 100% waste
- Empty Premium P3v3: **$876/month** → 100% waste

**Confidence Level**:
- **Critical** (95%+): Empty >90 days
- **High** (85-94%): Empty 60-89 days
- **Medium** (70-84%): Empty 30-59 days

---

### Scenario 2: Premium Tier in Dev/Test Environment
**Detection Logic**: Premium tier (P1v2+, P1v3+, Isolated) with environment tags indicating dev/test/staging.

```python
def detect_premium_in_dev_test(subscription_id: str) -> list:
    """
    Detect Premium App Service Plans in non-production environments.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_plans = []

    premium_tiers = ['Premium', 'PremiumV2', 'PremiumV3', 'Isolated']
    dev_keywords = ['dev', 'test', 'staging', 'qa', 'development', 'nonprod', 'uat', 'sandbox']

    for plan in web_client.app_service_plans.list():
        # Check if Premium tier
        if plan.sku.tier not in premium_tiers:
            continue

        # Check environment indicators
        tags = plan.tags or {}
        environment = tags.get('Environment', tags.get('environment', '')).lower()
        resource_group = plan.id.split('/')[4].lower()
        plan_name = plan.name.lower()

        # Check if dev/test environment
        is_dev_test = (
            any(keyword in environment for keyword in dev_keywords) or
            any(keyword in resource_group for keyword in dev_keywords) or
            any(keyword in plan_name for keyword in dev_keywords)
        )

        if is_dev_test:
            # Calculate savings by downsizing
            current_cost = calculate_plan_cost(plan.sku)
            recommended_sku = recommend_dev_test_sku(plan.sku.name)
            recommended_cost = get_sku_cost(recommended_sku)
            monthly_savings = current_cost - recommended_cost

            wasteful_plans.append({
                'resource_id': plan.id,
                'name': plan.name,
                'resource_group': plan.id.split('/')[4],
                'location': plan.location,
                'sku_name': plan.sku.name,
                'sku_tier': plan.sku.tier,
                'environment': environment or 'detected from naming',
                'current_monthly_cost': current_cost,
                'recommended_sku': recommended_sku,
                'recommended_monthly_cost': recommended_cost,
                'estimated_monthly_savings': round(monthly_savings, 2),
                'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                'confidence': 'high',
                'recommendation': f'Downgrade from {plan.sku.name} to {recommended_sku} for dev/test',
                'scenario': 'app_service_premium_in_dev',
                'metadata': {
                    'detection_method': 'tags' if environment else 'naming_convention',
                    'apps_count': count_apps_on_plan(web_client, plan.id)
                }
            })

    return wasteful_plans

def recommend_dev_test_sku(premium_sku: str) -> str:
    """Recommend appropriate dev/test SKU."""
    recommendations = {
        'P1v2': 'B2',   # Premium v2 → Basic
        'P2v2': 'B3',
        'P3v2': 'S1',
        'P0v3': 'B2',   # Premium v3 → Basic or Standard
        'P1v3': 'S1',
        'P2v3': 'S2',
        'P3v3': 'S3',
        'I1v2': 'S1',   # Isolated → Standard
        'I2v2': 'S2',
        'I3v2': 'S3',
    }
    return recommendations.get(premium_sku, 'B2')

def get_sku_cost(sku_name: str) -> float:
    """Get cost for a specific SKU."""
    sku_prices = {
        'B1': 13.14, 'B2': 55.48, 'B3': 104.03,
        'S1': 70.08, 'S2': 140.16, 'S3': 280.32,
        'P1v2': 146.00, 'P2v2': 292.00, 'P3v2': 584.00,
        'P0v3': 83.95, 'P1v3': 219.00, 'P2v3': 438.00, 'P3v3': 876.00,
    }
    return sku_prices.get(sku_name, 70.08)

def count_apps_on_plan(web_client, plan_id: str) -> int:
    """Count apps deployed on a plan."""
    apps = [app for app in web_client.web_apps.list() if app.server_farm_id == plan_id]
    return len(apps)
```

**Cost Impact**:
- Premium P1v2 ($146) → Basic B2 ($55) = **$91/month savings** (62%)
- Premium P1v3 ($219) → Standard S1 ($70) = **$149/month savings** (68%)
- Premium P3v3 ($876) → Standard S3 ($280) = **$596/month savings** (68%)

**Confidence Level**: **High** (90%) - Dev/test environments rarely need Premium features

---

### Scenario 3: No Auto-Scale Configured
**Detection Logic**: Standard/Premium plan with fixed instance count and no auto-scale rules configured.

```python
from azure.mgmt.monitor import MonitorManagementClient

def detect_no_autoscale(subscription_id: str) -> list:
    """
    Detect App Service Plans without auto-scale configured.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    monitor_client = MonitorManagementClient(credential, subscription_id)

    wasteful_plans = []

    for plan in web_client.app_service_plans.list():
        # Only check plans that support auto-scale (Standard+)
        if plan.sku.tier not in ['Standard', 'Premium', 'PremiumV2', 'PremiumV3', 'Isolated']:
            continue

        # Check if multiple instances (fixed scale)
        if plan.number_of_workers <= 1:
            continue  # Single instance, auto-scale not beneficial

        # Check for auto-scale settings
        resource_group = plan.id.split('/')[4]

        try:
            autoscale_settings = list(monitor_client.autoscale_settings.list_by_resource_group(resource_group))

            # Find settings targeting this plan
            plan_autoscale = [
                setting for setting in autoscale_settings
                if plan.id in setting.target_resource_uri
            ]

            if len(plan_autoscale) == 0:
                # No auto-scale configured
                current_cost = calculate_plan_cost(plan.sku)

                # Estimate potential savings with auto-scale
                # Assumption: Auto-scale can reduce instances by 40-50% during off-peak
                avg_instance_reduction = plan.number_of_workers * 0.45
                cost_per_instance = current_cost / plan.number_of_workers
                potential_monthly_savings = avg_instance_reduction * cost_per_instance

                wasteful_plans.append({
                    'resource_id': plan.id,
                    'name': plan.name,
                    'resource_group': resource_group,
                    'location': plan.location,
                    'sku_name': plan.sku.name,
                    'sku_tier': plan.sku.tier,
                    'current_instance_count': plan.number_of_workers,
                    'current_monthly_cost': current_cost,
                    'estimated_monthly_savings': round(potential_monthly_savings, 2),
                    'waste_percentage': round((potential_monthly_savings / current_cost) * 100, 1),
                    'confidence': 'medium',
                    'recommendation': f'Enable auto-scale (min: 1, max: {plan.number_of_workers}) to reduce costs',
                    'scenario': 'app_service_no_autoscale',
                    'metadata': {
                        'autoscale_available': True,
                        'current_instances': plan.number_of_workers,
                        'apps_count': count_apps_on_plan(web_client, plan.id)
                    }
                })

        except Exception as e:
            continue

    return wasteful_plans
```

**Cost Impact**:
- 3× S1 instances always-on: **$210/month**
- With auto-scale (avg 1.5 instances): **$105/month**
- **Savings: $105/month** (50%)

**Confidence Level**:
- **Medium** (65%): Without usage metrics
- **High** (85%): With Phase 2 CPU/memory metrics confirming low utilization

---

### Scenario 4: Always On Enabled for Low-Traffic Apps
**Detection Logic**: Always On feature enabled for apps with low expected traffic (based on tags or heuristics).

```python
def detect_always_on_low_traffic(subscription_id: str) -> list:
    """
    Detect apps with Always On enabled that may not need it.

    Phase 1: Uses tags and heuristics
    Phase 2: Uses actual request metrics
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_apps = []

    for app in web_client.web_apps.list():
        # Skip if Free/Shared tier (Always On not available)
        plan = web_client.app_service_plans.get(
            app.id.split('/')[4],
            app.server_farm_id.split('/')[-1]
        )

        if plan.sku.tier in ['Free', 'Shared']:
            continue

        # Get app configuration
        try:
            config = web_client.web_apps.get_configuration(
                app.id.split('/')[4],
                app.name
            )

            if config.always_on:
                # Check if app is likely low-traffic
                tags = app.tags or {}
                traffic_level = tags.get('traffic', tags.get('usage', '')).lower()

                is_low_traffic = (
                    'low' in traffic_level or
                    'infrequent' in traffic_level or
                    'testing' in traffic_level
                )

                if is_low_traffic:
                    plan_cost = calculate_plan_cost(plan.sku)
                    apps_on_plan = count_apps_on_plan(web_client, plan.id)

                    # Always On adds ~10-15% overhead
                    always_on_overhead = plan_cost * 0.125  # 12.5% average
                    per_app_overhead = always_on_overhead / max(apps_on_plan, 1)

                    wasteful_apps.append({
                        'resource_id': app.id,
                        'name': app.name,
                        'resource_group': app.id.split('/')[4],
                        'location': app.location,
                        'plan_name': plan.name,
                        'sku_name': plan.sku.name,
                        'always_on': True,
                        'traffic_level': traffic_level or 'unknown',
                        'estimated_monthly_overhead': round(per_app_overhead, 2),
                        'waste_percentage': 12.5,
                        'confidence': 'medium',
                        'recommendation': 'Disable Always On for low-traffic app to reduce costs',
                        'scenario': 'app_service_always_on_low_traffic',
                        'metadata': {
                            'detection_method': 'tags',
                            'needs_phase2_validation': True
                        }
                    })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**:
- Always On adds **10-15% overhead** to plan cost
- Standard S1 with Always On: $70/month → Without: $61/month = **$9/month** savings
- Premium P1v2 with Always On: $146/month → Without: $128/month = **$18/month** savings

**Confidence Level**: **Medium** (60%) - Requires Phase 2 request metrics for high confidence

---

### Scenario 5: Unused Deployment Slots
**Detection Logic**: Staging/test deployment slots created but never deployed or swapped (>90 days).

```python
def detect_unused_deployment_slots(subscription_id: str) -> list:
    """
    Detect unused deployment slots consuming resources.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_slots = []

    for app in web_client.web_apps.list():
        # Check if plan supports slots (Standard+)
        plan = web_client.app_service_plans.get(
            app.id.split('/')[4],
            app.server_farm_id.split('/')[-1]
        )

        if plan.sku.tier not in ['Standard', 'Premium', 'PremiumV2', 'PremiumV3', 'Isolated']:
            continue

        # List slots for this app
        try:
            slots = list(web_client.web_apps.list_slots(
                app.id.split('/')[4],
                app.name
            ))

            for slot in slots:
                # Skip production slot
                if slot.name.split('/')[-1] == app.name:
                    continue

                # Check slot age and usage
                if slot.last_modified_time_utc:
                    slot_age_days = (datetime.utcnow() - slot.last_modified_time_utc).days

                    if slot_age_days >= 90:
                        # Slot unused for 90+ days
                        plan_cost = calculate_plan_cost(plan.sku)
                        apps_on_plan = count_apps_on_plan(web_client, plan.id)

                        # Each slot = additional instance cost
                        per_slot_cost = plan_cost / max(apps_on_plan, 1)

                        wasteful_slots.append({
                            'resource_id': slot.id,
                            'name': slot.name,
                            'app_name': app.name,
                            'resource_group': app.id.split('/')[4],
                            'plan_name': plan.name,
                            'slot_age_days': slot_age_days,
                            'last_modified': slot.last_modified_time_utc.isoformat(),
                            'estimated_monthly_waste': round(per_slot_cost, 2),
                            'waste_percentage': 100,
                            'confidence': 'high',
                            'recommendation': 'Delete unused deployment slot (not swapped in 90+ days)',
                            'scenario': 'app_service_unused_deployment_slots',
                            'metadata': {
                                'slot_name': slot.name.split('/')[-1],
                                'state': slot.state
                            }
                        })

        except Exception as e:
            continue

    return wasteful_slots
```

**Cost Impact**:
- Each slot = **additional instance cost**
- App on S1 + 2 unused slots = 3× $70 = **$210/month** (vs $70 for app only)
- **Waste: $140/month** from 2 unused slots

**Confidence Level**: **High** (85%) - Slots unused for 90+ days are likely abandoned

---

### Scenario 6: Over-Provisioned App Service Plan
**Detection Logic**: Premium tier plan with single small app or very few apps (heuristic-based, without metrics).

```python
def detect_overprovisioned_plan(subscription_id: str) -> list:
    """
    Detect over-provisioned plans based on configuration heuristics.

    Phase 1: Tier vs. app count analysis
    Phase 2: Confirmed with CPU/memory metrics
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_plans = []

    for plan in web_client.app_service_plans.list():
        # Only check Premium tiers
        if plan.sku.tier not in ['Premium', 'PremiumV2', 'PremiumV3']:
            continue

        # Count apps on plan
        apps_on_plan = count_apps_on_plan(web_client, plan.id)

        # Heuristic: Premium tier with 1-2 apps = likely over-provisioned
        if apps_on_plan <= 2:
            current_cost = calculate_plan_cost(plan.sku)

            # Recommend Standard tier for small app count
            recommended_sku = 'S1' if apps_on_plan == 1 else 'S2'
            recommended_cost = get_sku_cost(recommended_sku)
            monthly_savings = current_cost - recommended_cost

            wasteful_plans.append({
                'resource_id': plan.id,
                'name': plan.name,
                'resource_group': plan.id.split('/')[4],
                'location': plan.location,
                'sku_name': plan.sku.name,
                'sku_tier': plan.sku.tier,
                'apps_count': apps_on_plan,
                'current_monthly_cost': current_cost,
                'recommended_sku': recommended_sku,
                'recommended_monthly_cost': recommended_cost,
                'estimated_monthly_savings': round(monthly_savings, 2),
                'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                'confidence': 'medium',
                'recommendation': f'Downgrade from {plan.sku.name} to {recommended_sku} ({apps_on_plan} app{"s" if apps_on_plan > 1 else ""})',
                'scenario': 'app_service_overprovisioned_plan',
                'metadata': {
                    'detection_method': 'app_count_heuristic',
                    'needs_phase2_validation': True
                }
            })

    return wasteful_plans
```

**Cost Impact**:
- Premium P1v2 ($146) with 1 app → Standard S1 ($70) = **$76/month savings** (52%)
- Premium P1v3 ($219) with 2 apps → Standard S2 ($140) = **$79/month savings** (36%)

**Confidence Level**: **Medium** (65%) without metrics, **High** (85%) with Phase 2 CPU/memory validation

---

### Scenario 7: Stopped Apps on Paid Plans
**Detection Logic**: Apps in "Stopped" state for >30 days on Basic+ tier plans (still consuming plan capacity).

```python
def detect_stopped_apps_on_paid_plans(subscription_id: str) -> list:
    """
    Detect stopped apps on paid plans (wasting capacity).
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_apps = []

    for app in web_client.web_apps.list():
        # Check if app is stopped
        if app.state != 'Stopped':
            continue

        # Get plan details
        plan = web_client.app_service_plans.get(
            app.id.split('/')[4],
            app.server_farm_id.split('/')[-1]
        )

        # Skip Free/Shared tiers (minimal cost)
        if plan.sku.tier in ['Free', 'Shared']:
            continue

        # Check how long stopped
        if app.last_modified_time_utc:
            stopped_days = (datetime.utcnow() - app.last_modified_time_utc).days

            if stopped_days >= 30:
                plan_cost = calculate_plan_cost(plan.sku)
                apps_on_plan = count_apps_on_plan(web_client, plan.id)

                # Stopped apps still consume plan capacity
                # If app is stopped long-term, should delete or move to Free tier
                per_app_cost = plan_cost / max(apps_on_plan, 1)

                confidence = 'high' if stopped_days >= 60 else 'medium'

                wasteful_apps.append({
                    'resource_id': app.id,
                    'name': app.name,
                    'resource_group': app.id.split('/')[4],
                    'plan_name': plan.name,
                    'sku_name': plan.sku.name,
                    'state': app.state,
                    'stopped_days': stopped_days,
                    'last_modified': app.last_modified_time_utc.isoformat(),
                    'estimated_monthly_waste': round(per_app_cost, 2),
                    'waste_percentage': 100,
                    'confidence': confidence,
                    'recommendation': 'Delete stopped app or move to Free tier',
                    'scenario': 'app_service_stopped_app_on_paid_plan',
                    'metadata': {
                        'apps_on_plan': apps_on_plan
                    }
                })

    return wasteful_apps
```

**Cost Impact**:
- Stopped app on S1 plan (3 apps total) = **$23/month** waste (1/3 of $70)
- Should delete or move to Free tier

**Confidence Level**:
- **High** (85%): Stopped >60 days
- **Medium** (75%): Stopped 30-59 days

---

### Scenario 8: Multiple Plans - Consolidation Possible
**Detection Logic**: Multiple App Service Plans in same region/resource group that could be consolidated into fewer plans.

```python
def detect_plan_consolidation_opportunities(subscription_id: str) -> list:
    """
    Detect multiple plans that could be consolidated.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    # Group plans by region and tier
    plans_by_region_tier = {}

    for plan in web_client.app_service_plans.list():
        # Skip Free/Shared (can't consolidate)
        if plan.sku.tier in ['Free', 'Shared']:
            continue

        key = f"{plan.location}_{plan.sku.tier}"

        if key not in plans_by_region_tier:
            plans_by_region_tier[key] = []

        plans_by_region_tier[key].append(plan)

    consolidation_opportunities = []

    for key, plans in plans_by_region_tier.items():
        if len(plans) <= 1:
            continue

        location, tier = key.split('_', 1)

        # Calculate total apps across all plans
        total_apps = sum(count_apps_on_plan(web_client, p.id) for p in plans)
        total_cost = sum(calculate_plan_cost(p.sku) for p in plans)

        # Check if could fit into 1-2 plans
        # Basic: max 3 instances, Standard: max 10, Premium: max 30
        max_capacity = {
            'Basic': 3 * 10,      # 3 instances × ~10 apps/instance
            'Standard': 10 * 10,  # 10 instances × ~10 apps/instance
            'Premium': 30 * 10,
            'PremiumV2': 30 * 10,
            'PremiumV3': 30 * 10,
        }.get(tier, 10)

        if total_apps <= max_capacity:
            # Could consolidate
            # Estimate consolidated cost
            if len(plans) <= 2:
                continue  # Already optimal

            # Recommend consolidating to 1-2 plans
            avg_sku = plans[0].sku.name  # Use first plan's SKU as reference
            consolidated_plan_count = max(1, len(plans) // 3)
            consolidated_cost = get_sku_cost(avg_sku) * consolidated_plan_count

            monthly_savings = total_cost - consolidated_cost

            if monthly_savings > 10:  # Only flag if savings >$10/month
                consolidation_opportunities.append({
                    'location': location,
                    'tier': tier,
                    'plan_count': len(plans),
                    'plan_names': [p.name for p in plans],
                    'total_apps': total_apps,
                    'current_total_cost': round(total_cost, 2),
                    'recommended_plan_count': consolidated_plan_count,
                    'estimated_consolidated_cost': round(consolidated_cost, 2),
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / total_cost) * 100, 1),
                    'confidence': 'medium',
                    'recommendation': f'Consolidate {len(plans)} plans into {consolidated_plan_count} plan(s)',
                    'scenario': 'app_service_multiple_plans_consolidation',
                    'metadata': {
                        'avg_apps_per_plan': round(total_apps / len(plans), 1)
                    }
                })

    return consolidation_opportunities
```

**Cost Impact**:
- 3× S1 plans ($210) → 1× S2 plan ($140) = **$70/month savings** (33%)
- 4× S1 plans ($280) → 2× S1 plans ($140) = **$140/month savings** (50%)

**Confidence Level**: **Medium** (70%) - Requires validation that apps are compatible

---

### Scenario 9: VNet Integration Unused
**Detection Logic**: Premium tier with VNet integration enabled but not actively used (no private resources accessed).

```python
def detect_vnet_integration_unused(subscription_id: str) -> list:
    """
    Detect Premium plans with unused VNet integration.

    Note: Requires Premium tier, so if not needed, can downgrade.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_plans = []

    for plan in web_client.app_service_plans.list():
        # Only Premium/Isolated support VNet integration
        if plan.sku.tier not in ['Premium', 'PremiumV2', 'PremiumV3', 'Isolated']:
            continue

        # Check if any apps have VNet connections
        apps_on_plan = [
            app for app in web_client.web_apps.list()
            if app.server_farm_id == plan.id
        ]

        has_vnet_connection = False

        for app in apps_on_plan:
            try:
                vnet_connections = web_client.web_apps.list_vnet_connections(
                    app.id.split('/')[4],
                    app.name
                )

                if len(list(vnet_connections)) > 0:
                    has_vnet_connection = True
                    break

            except Exception:
                continue

        if not has_vnet_connection:
            # Premium tier but no VNet usage
            # Could potentially downgrade to Standard
            current_cost = calculate_plan_cost(plan.sku)

            # Recommend Standard tier
            recommended_sku = 'S1' if plan.sku.name in ['P1v2', 'P0v3', 'P1v3'] else 'S2'
            recommended_cost = get_sku_cost(recommended_sku)
            monthly_savings = current_cost - recommended_cost

            wasteful_plans.append({
                'resource_id': plan.id,
                'name': plan.name,
                'resource_group': plan.id.split('/')[4],
                'sku_name': plan.sku.name,
                'apps_count': len(apps_on_plan),
                'vnet_integration_used': False,
                'current_monthly_cost': current_cost,
                'recommended_sku': recommended_sku,
                'recommended_monthly_cost': recommended_cost,
                'estimated_monthly_savings': round(monthly_savings, 2),
                'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                'confidence': 'medium',
                'recommendation': f'Downgrade to {recommended_sku} - VNet integration not used',
                'scenario': 'app_service_vnet_integration_unused',
                'metadata': {
                    'needs_validation': True
                }
            })

    return wasteful_plans
```

**Cost Impact**:
- Premium P1v2 ($146) without VNet usage → Standard S1 ($70) = **$76/month savings** (52%)

**Confidence Level**: **Medium** (60%) - Requires validation that VNet isn't needed for other reasons

---

### Scenario 10: Old Runtime Version
**Detection Logic**: Apps running on deprecated or unsupported runtimes (.NET Framework 4.5, PHP 5.6, Node 6.x, Python 2.7).

```python
def detect_old_runtime_versions(subscription_id: str) -> list:
    """
    Detect apps with deprecated runtime versions.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    # Deprecated runtimes
    deprecated_runtimes = {
        '.NET Framework 4.5': '2016-01-12',
        '.NET Framework 4.6': '2022-04-26',
        'PHP 5.6': '2018-12-31',
        'PHP 7.0': '2018-12-03',
        'PHP 7.1': '2019-12-01',
        'Node 6': '2019-04-30',
        'Node 8': '2019-12-31',
        'Node 10': '2021-04-30',
        'Python 2.7': '2020-01-01',
        'Python 3.6': '2021-12-23',
    }

    wasteful_apps = []

    for app in web_client.web_apps.list():
        try:
            config = web_client.web_apps.get_configuration(
                app.id.split('/')[4],
                app.name
            )

            # Check runtime version
            runtime = None

            if config.net_framework_version:
                runtime = f".NET Framework {config.net_framework_version}"
            elif config.php_version:
                runtime = f"PHP {config.php_version}"
            elif config.node_version:
                runtime = f"Node {config.node_version}"
            elif config.python_version:
                runtime = f"Python {config.python_version}"
            elif config.linux_fx_version:
                # Parse Linux runtime string (e.g., "DOTNETCORE|3.1", "NODE|14-lts")
                runtime = config.linux_fx_version

            # Check if deprecated
            is_deprecated = False
            for deprecated_runtime, eol_date in deprecated_runtimes.items():
                if runtime and deprecated_runtime.lower() in runtime.lower():
                    is_deprecated = True
                    break

            if is_deprecated:
                wasteful_apps.append({
                    'resource_id': app.id,
                    'name': app.name,
                    'resource_group': app.id.split('/')[4],
                    'runtime': runtime,
                    'eol_date': eol_date,
                    'waste_percentage': 0,  # Not direct cost waste
                    'confidence': 'high',
                    'recommendation': 'Upgrade to supported runtime version (security risk)',
                    'scenario': 'app_service_old_runtime_version',
                    'metadata': {
                        'security_risk': 'high',
                        'compliance_risk': 'medium'
                    }
                })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**: No direct cost savings, but **security and compliance risk**

**Confidence Level**: **High** (90%) - Deprecated runtimes are objectively risky

---

## Phase 2 Scenarios - Metrics-Based Detection

### Scenario 11: Low CPU Utilization (<10% Average Over 30 Days)
**Detection Logic**: App Service Plan with average CPU utilization <10% over 30 days.

```python
from azure.monitor.query import MetricsQueryClient
from datetime import datetime, timedelta

def detect_low_cpu_utilization(subscription_id: str) -> list:
    """
    Detect App Service Plans with low CPU utilization.

    Requires: azure-monitor-query==1.3.0
    Permission: Monitoring Reader
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_plans = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for plan in web_client.app_service_plans.list():
        # Skip Free/Shared
        if plan.sku.tier in ['Free', 'Shared']:
            continue

        try:
            # Query CPU metrics
            response = metrics_client.query_resource(
                resource_uri=plan.id,
                metric_names=["CpuPercentage"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            cpu_values = []
            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average is not None:
                            cpu_values.append(data_point.average)

            if not cpu_values:
                continue

            avg_cpu = sum(cpu_values) / len(cpu_values)

            if avg_cpu < 10:  # <10% CPU
                # Recommend downsizing
                current_sku = plan.sku.name
                recommended_sku = suggest_downsize_sku(current_sku)

                current_cost = calculate_plan_cost(plan.sku)
                recommended_cost = get_sku_cost(recommended_sku)
                monthly_savings = current_cost - recommended_cost

                wasteful_plans.append({
                    'resource_id': plan.id,
                    'name': plan.name,
                    'resource_group': plan.id.split('/')[4],
                    'sku_name': plan.sku.name,
                    'avg_cpu_percent': round(avg_cpu, 2),
                    'measurement_period_days': 30,
                    'samples_analyzed': len(cpu_values),
                    'recommended_sku': recommended_sku,
                    'current_monthly_cost': current_cost,
                    'recommended_monthly_cost': recommended_cost,
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                    'confidence': 'high',
                    'recommendation': f'Downsize from {current_sku} to {recommended_sku} (avg CPU {avg_cpu:.1f}%)',
                    'scenario': 'app_service_low_cpu_utilization',
                    'metadata': {
                        'min_cpu': round(min(cpu_values), 2),
                        'max_cpu': round(max(cpu_values), 2),
                        'p95_cpu': round(sorted(cpu_values)[int(len(cpu_values) * 0.95)], 2)
                    }
                })

        except Exception as e:
            continue

    return wasteful_plans

def suggest_downsize_sku(current_sku: str) -> str:
    """Suggest smaller SKU based on low CPU."""
    downsize_map = {
        'S2': 'S1',
        'S3': 'S2',
        'P1v2': 'S1',
        'P2v2': 'S2',
        'P3v2': 'S3',
        'P1v3': 'S1',
        'P2v3': 'S2',
        'P3v3': 'S3',
        'B2': 'B1',
        'B3': 'B2',
    }
    return downsize_map.get(current_sku, 'S1')
```

**Cost Impact**:
- S2 ($140) with 8% CPU → S1 ($70) = **$70/month savings** (50%)
- P1v2 ($146) with 7% CPU → S1 ($70) = **$76/month savings** (52%)

**Confidence Level**: **High** (85%) - 30 days of metrics is strong evidence

---

### Scenario 12: Low Memory Utilization (<30% Average Over 30 Days)
**Detection Logic**: Average memory utilization <30% over 30 days.

```python
def detect_low_memory_utilization(subscription_id: str) -> list:
    """
    Detect App Service Plans with low memory utilization.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_plans = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for plan in web_client.app_service_plans.list():
        if plan.sku.tier in ['Free', 'Shared']:
            continue

        try:
            response = metrics_client.query_resource(
                resource_uri=plan.id,
                metric_names=["MemoryPercentage"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            memory_values = []
            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average is not None:
                            memory_values.append(data_point.average)

            if not memory_values:
                continue

            avg_memory = sum(memory_values) / len(memory_values)

            if avg_memory < 30:  # <30% memory
                current_sku = plan.sku.name
                recommended_sku = suggest_downsize_sku(current_sku)

                current_cost = calculate_plan_cost(plan.sku)
                recommended_cost = get_sku_cost(recommended_sku)
                monthly_savings = current_cost - recommended_cost

                wasteful_plans.append({
                    'resource_id': plan.id,
                    'name': plan.name,
                    'resource_group': plan.id.split('/')[4],
                    'sku_name': plan.sku.name,
                    'avg_memory_percent': round(avg_memory, 2),
                    'measurement_period_days': 30,
                    'samples_analyzed': len(memory_values),
                    'recommended_sku': recommended_sku,
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                    'confidence': 'high',
                    'recommendation': f'Downsize from {current_sku} to {recommended_sku} (avg memory {avg_memory:.1f}%)',
                    'scenario': 'app_service_low_memory_utilization',
                    'metadata': {
                        'min_memory': round(min(memory_values), 2),
                        'max_memory': round(max(memory_values), 2)
                    }
                })

        except Exception as e:
            continue

    return wasteful_plans
```

**Cost Impact**: Similar to CPU scenario - **$50-76/month** savings depending on tier

**Confidence Level**: **High** (85%)

---

### Scenario 13: Low Request Count (<100 Requests/Day)
**Detection Logic**: Very low HTTP request volume (<100 requests/day average over 30 days).

```python
def detect_low_request_count(subscription_id: str) -> list:
    """
    Detect apps with very low HTTP traffic.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_apps = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for app in web_client.web_apps.list():
        try:
            response = metrics_client.query_resource(
                resource_uri=app.id,
                metric_names=["Requests"],
                timespan=(start_time, end_time),
                granularity=timedelta(days=1),
                aggregations=["Total"]
            )

            request_counts = []
            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.total is not None:
                            request_counts.append(data_point.total)

            if not request_counts:
                continue

            total_requests = sum(request_counts)
            avg_requests_per_day = total_requests / 30

            if avg_requests_per_day < 100:  # <100 requests/day
                # Get plan cost
                plan = web_client.app_service_plans.get(
                    app.id.split('/')[4],
                    app.server_farm_id.split('/')[-1]
                )

                plan_cost = calculate_plan_cost(plan.sku)
                apps_on_plan = count_apps_on_plan(web_client, plan.id)
                per_app_cost = plan_cost / max(apps_on_plan, 1)

                # Recommend Azure Functions (consumption model)
                functions_cost = 5.00  # Estimated $5/month for <100 req/day

                monthly_savings = per_app_cost - functions_cost

                wasteful_apps.append({
                    'resource_id': app.id,
                    'name': app.name,
                    'resource_group': app.id.split('/')[4],
                    'total_requests_30_days': int(total_requests),
                    'avg_requests_per_day': round(avg_requests_per_day, 0),
                    'current_monthly_cost': round(per_app_cost, 2),
                    'recommended_alternative': 'Azure Functions (Consumption)',
                    'estimated_alternative_cost': functions_cost,
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / per_app_cost) * 100, 1),
                    'confidence': 'high',
                    'recommendation': 'Migrate to Azure Functions for low-traffic workload',
                    'scenario': 'app_service_low_request_count',
                    'metadata': {
                        'measurement_period_days': 30,
                        'plan_sku': plan.sku.name
                    }
                })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**:
- App on S1 plan (<100 req/day): **$70/month**
- Azure Functions consumption: **$5/month**
- **Savings: $65/month** (93%)

**Confidence Level**: **High** (90%) - Very low traffic is strong indicator

---

### Scenario 14: No Traffic During Business Hours
**Detection Logic**: Zero HTTP requests during business hours (9 AM - 5 PM) for 30 days.

```python
def detect_no_traffic_business_hours(subscription_id: str) -> list:
    """
    Detect apps with no traffic during business hours.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_apps = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for app in web_client.web_apps.list():
        try:
            response = metrics_client.query_resource(
                resource_uri=app.id,
                metric_names=["Requests"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Total"]
            )

            business_hours_requests = []

            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.total is not None:
                            # Check if business hours (9 AM - 5 PM)
                            timestamp = data_point.timestamp
                            hour = timestamp.hour
                            weekday = timestamp.weekday()

                            if 9 <= hour < 17 and weekday < 5:  # Monday-Friday, 9-5
                                business_hours_requests.append(data_point.total)

            if not business_hours_requests:
                continue

            total_business_requests = sum(business_hours_requests)

            if total_business_requests < 10:  # <10 requests in 30 days during business hours
                # App abandoned or only used off-hours
                plan = web_client.app_service_plans.get(
                    app.id.split('/')[4],
                    app.server_farm_id.split('/')[-1]
                )

                plan_cost = calculate_plan_cost(plan.sku)
                apps_on_plan = count_apps_on_plan(web_client, plan.id)
                per_app_cost = plan_cost / max(apps_on_plan, 1)

                wasteful_apps.append({
                    'resource_id': app.id,
                    'name': app.name,
                    'resource_group': app.id.split('/')[4],
                    'business_hours_requests_30_days': int(total_business_requests),
                    'estimated_monthly_cost': round(per_app_cost, 2),
                    'waste_percentage': 100,
                    'confidence': 'critical',
                    'recommendation': 'Delete app - no business hours traffic (likely abandoned)',
                    'scenario': 'app_service_no_traffic_business_hours',
                    'metadata': {
                        'measurement_period_days': 30,
                        'business_hours': '9 AM - 5 PM (weekdays)'
                    }
                })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**: **100% waste** if app is abandoned

**Confidence Level**: **Critical** (95%) - No business hours traffic is very strong indicator

---

### Scenario 15: High HTTP Error Rate (>50%)
**Detection Logic**: HTTP 5xx error rate >50% over 7 days.

```python
def detect_high_http_errors(subscription_id: str) -> list:
    """
    Detect apps with high HTTP error rates (broken apps wasting resources).
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_apps = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)

    for app in web_client.web_apps.list():
        try:
            response = metrics_client.query_resource(
                resource_uri=app.id,
                metric_names=["Http5xx", "Requests"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Total"]
            )

            http_5xx_count = 0
            total_requests = 0

            for metric in response.metrics:
                if metric.name == "Http5xx":
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.total:
                                http_5xx_count += data_point.total
                elif metric.name == "Requests":
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.total:
                                total_requests += data_point.total

            if total_requests == 0:
                continue

            error_rate = (http_5xx_count / total_requests) * 100

            if error_rate > 50:  # >50% error rate
                plan = web_client.app_service_plans.get(
                    app.id.split('/')[4],
                    app.server_farm_id.split('/')[-1]
                )

                plan_cost = calculate_plan_cost(plan.sku)
                apps_on_plan = count_apps_on_plan(web_client, plan.id)
                per_app_cost = plan_cost / max(apps_on_plan, 1)

                wasteful_apps.append({
                    'resource_id': app.id,
                    'name': app.name,
                    'resource_group': app.id.split('/')[4],
                    'http_5xx_count': int(http_5xx_count),
                    'total_requests': int(total_requests),
                    'error_rate_percent': round(error_rate, 1),
                    'estimated_monthly_cost': round(per_app_cost, 2),
                    'waste_percentage': 75,  # App broken = wasting resources
                    'confidence': 'high',
                    'recommendation': 'Fix app errors or stop app - >50% HTTP 5xx error rate',
                    'scenario': 'app_service_high_http_errors',
                    'metadata': {
                        'measurement_period_days': 7
                    }
                })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**: **75% waste** - App broken, serving errors instead of value

**Confidence Level**: **High** (85%)

---

### Scenario 16: Slow Response Time (>10 Seconds Average)
**Detection Logic**: Average HTTP response time >10 seconds over 30 days.

```python
def detect_slow_response_time(subscription_id: str) -> list:
    """
    Detect apps with severe performance issues.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_apps = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for app in web_client.web_apps.list():
        try:
            response = metrics_client.query_resource(
                resource_uri=app.id,
                metric_names=["AverageResponseTime"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            response_times = []

            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average:
                            response_times.append(data_point.average)

            if not response_times:
                continue

            avg_response_time = sum(response_times) / len(response_times)

            if avg_response_time > 10:  # >10 seconds
                plan = web_client.app_service_plans.get(
                    app.id.split('/')[4],
                    app.server_farm_id.split('/')[-1]
                )

                wasteful_apps.append({
                    'resource_id': app.id,
                    'name': app.name,
                    'resource_group': app.id.split('/')[4],
                    'avg_response_time_seconds': round(avg_response_time, 2),
                    'plan_sku': plan.sku.name,
                    'waste_percentage': 50,  # Severe performance issue
                    'confidence': 'medium',
                    'recommendation': 'Optimize app code or scale up plan - >10s response time',
                    'scenario': 'app_service_slow_response_time',
                    'metadata': {
                        'max_response_time': round(max(response_times), 2),
                        'measurement_period_days': 30
                    }
                })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**: Performance issue → either under-resourced (scale up) or code optimization needed

**Confidence Level**: **Medium** (70%) - Requires investigation

---

### Scenario 17: Auto-Scale Configured But Never Triggers
**Detection Logic**: Auto-scale enabled but instance count never changes over 30 days.

```python
def detect_autoscale_not_working(subscription_id: str) -> list:
    """
    Detect auto-scale misconfiguration.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)
    monitor_client = MonitorManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_plans = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for plan in web_client.app_service_plans.list():
        # Check if auto-scale is configured
        resource_group = plan.id.split('/')[4]

        try:
            autoscale_settings = list(monitor_client.autoscale_settings.list_by_resource_group(resource_group))

            plan_autoscale = [
                setting for setting in autoscale_settings
                if plan.id in setting.target_resource_uri
            ]

            if len(plan_autoscale) == 0:
                continue  # No autoscale

            # Query instance count over time
            response = metrics_client.query_resource(
                resource_uri=plan.id,
                metric_names=["InstanceCount"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=6),
                aggregations=["Average"]
            )

            instance_counts = []

            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average:
                            instance_counts.append(int(data_point.average))

            if not instance_counts:
                continue

            # Check variance
            import statistics
            stddev = statistics.stdev(instance_counts) if len(instance_counts) > 1 else 0

            if stddev < 0.5:  # Instance count never changes
                wasteful_plans.append({
                    'resource_id': plan.id,
                    'name': plan.name,
                    'resource_group': resource_group,
                    'sku_name': plan.sku.name,
                    'autoscale_enabled': True,
                    'instance_count_stddev': round(stddev, 2),
                    'min_instances_observed': min(instance_counts),
                    'max_instances_observed': max(instance_counts),
                    'waste_percentage': 20,  # Potential savings missed
                    'confidence': 'medium',
                    'recommendation': 'Review auto-scale rules - instance count never changes',
                    'scenario': 'app_service_autoscale_not_working',
                    'metadata': {
                        'measurement_period_days': 30,
                        'samples_analyzed': len(instance_counts)
                    }
                })

        except Exception as e:
            continue

    return wasteful_plans
```

**Cost Impact**: Missing potential **30-50% savings** from auto-scale

**Confidence Level**: **Medium** (70%)

---

### Scenario 18: Cold Start Time Excessive (>30 Seconds)
**Detection Logic**: App with Always On disabled experiencing >30 second cold starts (poor UX).

```python
def detect_cold_start_excessive(subscription_id: str) -> list:
    """
    Detect apps with excessive cold start times.

    Note: Requires Application Insights integration.
    """
    credential = DefaultAzureCredential()
    web_client = WebSiteManagementClient(credential, subscription_id)

    wasteful_apps = []

    for app in web_client.web_apps.list():
        try:
            config = web_client.web_apps.get_configuration(
                app.id.split('/')[4],
                app.name
            )

            # If Always On disabled, check for cold starts
            if not config.always_on:
                # Would require Application Insights query for cold start duration
                # Simplified for example: flag apps on Basic tier without Always On
                plan = web_client.app_service_plans.get(
                    app.id.split('/')[4],
                    app.server_farm_id.split('/')[-1]
                )

                if plan.sku.tier == 'Basic':
                    # Basic tier can experience cold starts
                    wasteful_apps.append({
                        'resource_id': app.id,
                        'name': app.name,
                        'resource_group': app.id.split('/')[4],
                        'always_on': False,
                        'plan_tier': plan.sku.tier,
                        'confidence': 'medium',
                        'recommendation': 'Enable Always On or upgrade to Standard+ to avoid cold starts',
                        'scenario': 'app_service_cold_start_excessive',
                        'metadata': {
                            'tradeoff': 'Always On adds 10-15% cost but improves UX'
                        }
                    })

        except Exception as e:
            continue

    return wasteful_apps
```

**Cost Impact**: Tradeoff between cold starts (poor UX) and Always On (10-15% higher cost)

**Confidence Level**: **Medium** (65%)

---

## Pricing Structure

### Azure App Service Plan Pricing (East US, Pay-As-You-Go)

#### Free & Shared Tiers
| Tier | vCPU Time | RAM | Storage | Custom Domains | SSL | Monthly Cost |
|------|-----------|-----|---------|----------------|-----|--------------|
| **F1 (Free)** | 60 min/day | 1 GB | 1 GB | No | No | **$0** |
| **D1 (Shared)** | 240 min/day | 1 GB | 1 GB | Yes | No | **$9.49** |

**Features**: Limited CPU time, no auto-scale, no deployment slots, no Always On

---

#### Basic Tier (B-series)
| SKU | vCPU | RAM | Storage | Max Instances | Monthly Cost | Use Case |
|-----|------|-----|---------|---------------|--------------|----------|
| **B1** | 1 | 1.75 GB | 10 GB | 3 | **$13.14** | Small web apps |
| **B2** | 2 | 3.5 GB | 10 GB | 3 | **$55.48** | Medium apps |
| **B3** | 4 | 7 GB | 10 GB | 3 | **$104.03** | Larger apps |

**Features**: Always On, custom domains, SSL, manual scale (up to 3 instances)
**Missing**: Auto-scale, deployment slots, backup, Traffic Manager

---

#### Standard Tier (S-series)
| SKU | vCPU | RAM | Storage | Max Instances | Monthly Cost | Use Case |
|-----|------|-----|---------|---------------|--------------|----------|
| **S1** | 1 | 1.75 GB | 50 GB | 10 | **$70.08** | Production apps |
| **S2** | 2 | 3.5 GB | 50 GB | 10 | **$140.16** | Medium production |
| **S3** | 4 | 7 GB | 50 GB | 10 | **$280.32** | Large production |

**Features**: **Auto-scale**, 5 deployment slots, daily backup, Traffic Manager
**Key Benefit**: Auto-scale can save 30-50% vs. fixed instances

---

#### Premium v2 Tier (Pv2-series)
| SKU | vCPU | RAM | Storage | Max Instances | Monthly Cost | Use Case |
|-----|------|-----|---------|---------------|--------------|----------|
| **P1v2** | 1 | 3.5 GB | 250 GB | 30 | **$146.00** | High performance |
| **P2v2** | 2 | 7 GB | 250 GB | 30 | **$292.00** | Very high perf |
| **P3v2** | 4 | 14 GB | 250 GB | 30 | **$584.00** | Enterprise |

**Features**: VNet integration, 20 deployment slots, better hardware, faster scaling

---

#### Premium v3 Tier (Pv3-series) - Better Price/Performance
| SKU | vCPU | RAM | Storage | Max Instances | Monthly Cost | Use Case |
|-----|------|-----|---------|---------------|--------------|----------|
| **P0v3** | 1 | 4 GB | 250 GB | 30 | **$83.95** | Cost-optimized premium |
| **P1v3** | 2 | 8 GB | 250 GB | 30 | **$219.00** | Better price/perf |
| **P2v3** | 4 | 16 GB | 250 GB | 30 | **$438.00** | High performance |
| **P3v3** | 8 | 32 GB | 250 GB | 30 | **$876.00** | Enterprise scale |

**Better Value**: ~20-30% better price/performance than v2

---

#### Isolated Tier (Iv2-series) - App Service Environment
| SKU | vCPU | RAM | Storage | Max Instances | Monthly Cost | Use Case |
|-----|------|-----|---------|---------------|--------------|----------|
| **I1v2** | 2 | 8 GB | 1 TB | 100 | **$438.00** | Dedicated VNet |
| **I2v2** | 4 | 16 GB | 1 TB | 100 | **$876.00** | High security |
| **I3v2** | 8 | 32 GB | 1 TB | 100 | **$1,753.00** | Enterprise isolated |

**Features**: Completely isolated environment, dedicated VNet, compliance requirements
**Additional Cost**: App Service Environment stamp fee (~$1,000/month)

---

### Cost Examples with Auto-Scale

**Scenario: 3-instance Standard S1 plan**

| Configuration | Cost Calculation | Monthly Cost |
|---------------|------------------|--------------|
| **Fixed 3 instances** | 3 × $70.08 | **$210.24** |
| **Auto-scale 1-3 (avg 1.5)** | 1.5 × $70.08 | **$105.12** |
| **Savings with auto-scale** | - | **$105.12 (50%)** |

---

## Required Azure Permissions

### Minimum RBAC Roles

**Phase 1 Detection (Configuration):**
- **Reader** role on Resource Group or Subscription

**Phase 2 Detection (Metrics):**
- **Monitoring Reader** role on Resource Group or Subscription

### Custom Role Definition (Recommended)

```json
{
  "Name": "CloudWaste App Service Scanner",
  "Description": "Read-only access to App Service plans, apps, and metrics for waste detection",
  "Actions": [
    "Microsoft.Web/serverfarms/read",
    "Microsoft.Web/sites/read",
    "Microsoft.Web/sites/config/read",
    "Microsoft.Web/sites/slots/read",
    "Microsoft.Insights/Metrics/Read",
    "Microsoft.Insights/DiagnosticSettings/Read",
    "Microsoft.Insights/AutoscaleSettings/Read"
  ],
  "NotActions": [],
  "AssignableScopes": ["/subscriptions/{subscription-id}"]
}
```

### Service Principal Setup

```bash
# Create service principal
az ad sp create-for-rbac --name "CloudWaste-AppService-Scanner" \
  --role "Reader" \
  --scopes "/subscriptions/{subscription-id}"

# Add Monitoring Reader role
az role assignment create \
  --assignee {service-principal-id} \
  --role "Monitoring Reader" \
  --scope "/subscriptions/{subscription-id}"
```

---

## Azure CLI Commands for Testing

### 1. Create Test App Service Plan and App

```bash
# Set variables
RESOURCE_GROUP="cloudwaste-test-rg"
LOCATION="eastus"
PLAN_NAME="test-appserviceplan"
APP_NAME="test-webapp-$(date +%s)"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Standard S1 App Service Plan
az appservice plan create \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku S1

# Expected cost: $70.08/month

# Create Web App
az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $PLAN_NAME \
  --runtime "NODE:18-lts"
```

### 2. Configure Auto-Scale

```bash
# Enable auto-scale with CPU-based rule
az monitor autoscale create \
  --resource $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --resource-type Microsoft.Web/serverfarms \
  --name autoscale-$PLAN_NAME \
  --min-count 1 \
  --max-count 5 \
  --count 2

# Add scale-out rule (CPU >70%)
az monitor autoscale rule create \
  --resource $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --autoscale-name autoscale-$PLAN_NAME \
  --scale out 1 \
  --condition "CpuPercentage > 70 avg 5m"

# Add scale-in rule (CPU <30%)
az monitor autoscale rule create \
  --resource $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --autoscale-name autoscale-$PLAN_NAME \
  --scale in 1 \
  --condition "CpuPercentage < 30 avg 5m"
```

### 3. Enable Always On

```bash
# Enable Always On (requires Basic+ tier)
az webapp config set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --always-on true

# Disable Always On
az webapp config set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --always-on false
```

### 4. Create Deployment Slot

```bash
# Create staging slot
az webapp deployment slot create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --slot staging

# Swap slots
az webapp deployment slot swap \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --slot staging \
  --target-slot production
```

### 5. Query Metrics

```bash
# Get App Service Plan resource ID
PLAN_ID=$(az appservice plan show \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "id" -o tsv)

# Get CPU percentage (last 30 days)
az monitor metrics list \
  --resource $PLAN_ID \
  --metric CpuPercentage \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table

# Get memory percentage
az monitor metrics list \
  --resource $PLAN_ID \
  --metric MemoryPercentage \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --aggregation Average \
  --output table

# Get HTTP requests (app level)
APP_ID=$(az webapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "id" -o tsv)

az monitor metrics list \
  --resource $APP_ID \
  --metric Requests \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --aggregation Total \
  --interval P1D \
  --output table
```

### 6. Scale Plan Up/Down

```bash
# Scale up to Premium P1v2
az appservice plan update \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku P1v2

# Scale down to Basic B2
az appservice plan update \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku B2
```

### 7. Stop and Start App

```bash
# Stop app (stops billing only if plan is empty)
az webapp stop \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Start app
az webapp start \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### 8. Cleanup

```bash
# Delete app
az webapp delete \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Delete App Service Plan
az appservice plan delete \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete resource group
az group delete --name $RESOURCE_GROUP --yes
```

---

## Comparison with Alternatives

### App Service vs Azure Functions vs Container Apps vs Static Web Apps

| Feature | App Service | Azure Functions | Container Apps | Static Web Apps |
|---------|-------------|-----------------|----------------|-----------------|
| **Pricing Model** | Per plan (hourly) | Consumption (per execution) | Consumption (per second) | Free or $9/month |
| **Min Cost** | $13-70/month | ~$0 (first 1M free) | ~$0 (scales to 0) | $0 |
| **Best For** | Traditional web apps | Event-driven, <5 min runtime | Microservices, containers | Static sites (React, Angular) |
| **Auto-Scale to 0** | ❌ No | ✅ Yes | ✅ Yes | N/A |
| **Cold Start** | 3-5 seconds (no Always On) | 1-3 seconds | 5-10 seconds | Instant |
| **Runtime Support** | .NET, Java, Node, PHP, Python | .NET, Java, Node, Python, PowerShell | Any container | Static HTML/JS/CSS |
| **Max Instances** | 30 (Premium) | 200 | Unlimited | N/A |
| **Deployment Slots** | ✅ Yes (Standard+) | ❌ No | ❌ No | ❌ No |
| **VNet Integration** | ✅ Yes (Premium+) | ✅ Yes (Premium) | ✅ Yes | ❌ No |
| **Waste Risk** | **HIGH** | **LOW** | **LOW** | **NONE** |

### When App Service = WASTE

| Current Setup | Better Alternative | Savings |
|---------------|-------------------|---------|
| App Service S1 with <100 requests/day | Azure Functions | **$65/month** (93%) |
| App Service for static React site | Static Web Apps | **$61-70/month** (87-100%) |
| App Service with single container | Container Apps | **$30-40/month** (43-57%) |
| Multiple small apps on separate plans | Consolidate into 1 plan | **$70-210/month** (33-75%) |

### When App Service = OPTIMAL

✅ **Use App Service When:**
- Traditional web applications (ASP.NET, Java Spring, Django, Express)
- Steady traffic (100-10,000 requests/day range)
- Need deployment slots for blue-green deployments
- Require Always On (no cold starts)
- Team familiar with PaaS (not Kubernetes)
- Need backup, custom domains, SSL out-of-the-box

❌ **Don't Use App Service When:**
- Very low traffic (<100 requests/day) → Use **Functions**
- Static website → Use **Static Web Apps**
- Event-driven workload → Use **Functions**
- Need to scale to zero → Use **Container Apps** or **Functions**
- Complex microservices → Use **AKS**

---

## Test Matrix

### Phase 1 Tests (Configuration-Based)

| Scenario | Test Setup | Expected Detection | Validation Command |
|----------|------------|-------------------|-------------------|
| 1. Empty plan | Create S1 plan, deploy 0 apps | HIGH confidence, 100% waste | `az appservice plan show --query 'numberOfSites'` → 0 |
| 2. Premium in dev | Create P1v2, tag Environment=dev | HIGH confidence, 62% waste | Check plan tier + tags |
| 3. No autoscale | Create S1 with 3 instances, no autoscale | MEDIUM confidence, 50% waste | `az monitor autoscale list` → empty |
| 4. Always On low traffic | Enable Always On, tag traffic=low | MEDIUM confidence, 12% waste | Check config.always_on |
| 5. Unused slots | Create staging slot 100 days ago | HIGH confidence, $70/slot | Check slot last_modified |
| 6. Over-provisioned | P1v2 with 1 app | MEDIUM confidence, 52% waste | Count apps on Premium plan |
| 7. Stopped app >30d | Stop app, wait 30 days | HIGH confidence, per-app waste | `az webapp show --query 'state'` → Stopped |
| 8. Multiple plans | Create 3× S1 plans in same region | MEDIUM confidence, $70-140/month | List plans by region |
| 9. VNet unused | Premium plan, no VNet connections | MEDIUM confidence, 52% waste | Check vnet_connections |
| 10. Old runtime | Deploy app with PHP 5.6 | HIGH confidence, security risk | Check config.php_version |

### Phase 2 Tests (Metrics-Based)

| Scenario | Test Setup | Expected Detection | Validation Metric |
|----------|------------|-------------------|-------------------|
| 11. Low CPU | S2 plan with minimal load for 30 days | HIGH confidence, 50% waste | CpuPercentage < 10% |
| 12. Low memory | S2 plan with <30% memory for 30 days | HIGH confidence, $50/month | MemoryPercentage < 30% |
| 13. Low requests | App with <100 requests/day for 30 days | HIGH confidence, 93% savings | Requests < 100/day |
| 14. No business hours traffic | App with 0 requests 9-5 weekdays | CRITICAL confidence, 100% waste | Requests (9-17h) = 0 |
| 15. High HTTP errors | App with >50% 5xx errors for 7 days | HIGH confidence, 75% waste | Http5xx / Requests > 50% |
| 16. Slow response | App with >10s response time | MEDIUM confidence, optimization needed | AverageResponseTime > 10s |
| 17. Autoscale not working | Autoscale enabled but instance count constant | MEDIUM confidence, missed savings | InstanceCount stddev < 0.5 |
| 18. Cold start excessive | Basic tier without Always On | MEDIUM confidence, UX tradeoff | Check tier + Always On status |

---

## Troubleshooting Guide

### Issue 1: Cannot List App Service Plans or Apps

**Symptoms:**
- `web_client.app_service_plans.list()` returns empty
- Error: `AuthenticationFailed` or `ResourceNotFound`

**Solution:**
```bash
# Verify permissions
az role assignment list \
  --assignee {service-principal-id} \
  --scope "/subscriptions/{subscription-id}"

# Test with Azure CLI
az appservice plan list --output table
```

---

### Issue 2: Auto-Scale Settings Not Found

**Symptoms:**
- `monitor_client.autoscale_settings.list_by_resource_group()` returns empty
- Plan has auto-scale but detection doesn't find it

**Solution:**
```python
# Check correct resource URI format
autoscale_settings = monitor_client.autoscale_settings.list_by_subscription()

for setting in autoscale_settings:
    if plan.id.lower() in setting.target_resource_uri.lower():
        print(f"Found autoscale: {setting.name}")
```

---

### Issue 3: Metrics Return No Data

**Symptoms:**
- CPU/Memory metrics return empty results
- Plan is new (<1 hour old)

**Solution:**
```bash
# Wait 15-30 minutes after plan creation
# Verify metrics are available
az monitor metrics list-definitions \
  --resource $PLAN_ID \
  --query "[].name.value" \
  --output table

# Check specific metric
az monitor metrics list \
  --resource $PLAN_ID \
  --metric CpuPercentage \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
```

---

## Business Impact Analysis

### Small Development Team (10 App Service Plans)

**Typical Setup:**
- 3 Premium P1v2 plans in dev/test
- 4 Standard S1 plans in production (no autoscale)
- 2 empty Basic B1 plans (forgotten)
- 1 plan with unused deployment slots

**Baseline Cost:**
- 3× P1v2: 3 × $146 = **$438/month**
- 4× S1: 4 × $70 = **$280/month**
- 2× B1: 2 × $13 = **$26/month**
- 1× S1 with 2 slots: 3 × $70 = **$210/month**
- **Total: $954/month** ($11,448/year)

**Waste Detected:**

| Scenario | Frequency | Monthly Waste | Annual Waste |
|----------|-----------|---------------|--------------|
| Premium in dev | 3 plans | $273 | $3,276 |
| No autoscale | 4 plans | $140 | $1,680 |
| Empty plans | 2 plans | $26 | $312 |
| Unused slots | 2 slots | $140 | $1,680 |
| Always On low traffic | 2 apps | $18 | $216 |
| **Total Waste** | **10 plans** | **$597** | **$7,164** |

**After CloudWaste Optimization:**
- Downgrade dev to Basic: Save $273/month
- Enable autoscale on prod: Save $140/month
- Delete empty plans: Save $26/month
- Delete unused slots: Save $140/month
- **Optimized Total: $357/month** ($4,284/year)

**Savings: $597/month** (**$7,164/year**) → **63% reduction**

---

### Enterprise Organization (200 App Service Plans)

**Typical Setup:**
- 50 Premium plans (mix P1v2, P2v2)
- 100 Standard plans (S1, S2, S3)
- 30 Basic plans
- 20 empty plans

**Baseline Cost:**
- 30× P1v2: 30 × $146 = $4,380/month
- 20× P2v2: 20 × $292 = $5,840/month
- 60× S1: 60 × $70 = $4,200/month
- 30× S2: 30 × $140 = $4,200/month
- 10× S3: 10 × $280 = $2,800/month
- 30× B1-B3: ~$1,500/month
- **Total: $22,920/month** ($275,040/year)

**Waste Detected:**

| Scenario | Frequency | Monthly Waste | Annual Waste |
|----------|-----------|---------------|--------------|
| Premium in dev/test | 20 plans | $1,820 | $21,840 |
| No autoscale | 60 plans | $3,150 | $37,800 |
| Empty plans | 20 plans | $1,200 | $14,400 |
| Low traffic (<100 req/day) | 30 apps | $1,950 | $23,400 |
| Plan consolidation | 40 plans | $2,800 | $33,600 |
| Stopped apps >30 days | 25 apps | $625 | $7,500 |
| Unused deployment slots | 30 slots | $2,100 | $25,200 |
| Always On low traffic | 40 apps | $360 | $4,320 |
| **Total Waste** | **200 plans** | **$14,005** | **$168,060** |

**After CloudWaste Optimization:**
- **Optimized Total: $8,915/month** ($106,980/year)

**Savings: $14,005/month** (**$168,060/year**) → **61% reduction**

**ROI:**
- CloudWaste subscription: $2,000/month (enterprise)
- Net savings: $12,005/month
- **ROI: 7,203% annually**

---

## Implementation Roadmap

### Phase 1: Simple Detection (Week 1-2)

**Goal**: Detect configuration-based waste.

**Tasks:**
1. Implement Azure Web SDK client (`azure-mgmt-web`)
2. Build Scenarios 1-10 (empty plans, premium in dev, no autoscale, etc.)
3. Create cost calculation engine
4. Test with 10 sample plans
5. Deploy to CloudWaste backend

**Expected Results:**
- 10 detection scenarios operational
- 50-60% of waste identified

---

### Phase 2: Metrics-Based Detection (Week 3-4)

**Goal**: Add Azure Monitor integration.

**Tasks:**
1. Integrate `azure-monitor-query==1.3.0`
2. Implement Scenarios 11-18 (low CPU, memory, requests, errors)
3. Add confidence level calculations
4. Test metrics collection for 30-day period

**Expected Results:**
- 18 detection scenarios operational
- 85%+ of waste identified

---

### Phase 3: Frontend Integration (Week 5)

**Goal**: Display App Service waste in dashboard.

**Tasks:**
1. Add "App Service Plans" resource type to frontend
2. Create plan detail pages (show apps, CPU/memory graphs)
3. Implement cost savings calculator
4. Add action buttons ("Delete Empty Plan", "Enable Auto-Scale", "Downgrade Tier")

**Expected Results:**
- App Service visible in main dashboard
- One-click remediation actions

---

### Phase 4: Automated Remediation (Week 6-8)

**Goal**: Auto-fix waste with user approval.

**Tasks:**
1. Implement auto-scale enablement
2. Implement plan tier changes
3. Implement plan deletion (with confirmation)
4. Add approval workflow
5. Add audit log

**Expected Results:**
- Users can enable "Auto-Fix" mode
- 60% of waste remediated automatically

---

## References

### Official Documentation

1. **Azure App Service Overview**
   https://learn.microsoft.com/en-us/azure/app-service/

2. **App Service Pricing**
   https://azure.microsoft.com/en-us/pricing/details/app-service/windows/

3. **Auto-Scale Best Practices**
   https://learn.microsoft.com/en-us/azure/app-service/manage-automatic-scaling

4. **Azure Web Python SDK**
   https://learn.microsoft.com/en-us/python/api/azure-mgmt-web/

5. **Azure Monitor Metrics**
   https://learn.microsoft.com/en-us/azure/app-service/web-sites-monitor

---

**Document Version**: 1.0
**Last Updated**: 2025-10-29
**Authors**: CloudWaste Team
**Coverage**: 18 waste detection scenarios (100% comprehensive)
**Estimated Detection Value**: $597 - $14,005/month per organization
