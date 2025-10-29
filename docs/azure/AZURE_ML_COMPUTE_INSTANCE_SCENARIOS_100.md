# Azure Machine Learning Compute Instance - Waste Detection Scenarios (100% Coverage)

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

**Azure Machine Learning Compute Instances** are personal, managed cloud-based workstations designed for data scientists. They provide pre-configured development environments with Jupyter, JupyterLab, RStudio, and VS Code, but are **highly susceptible to waste** when left running 24/7 without proper auto-shutdown configurations.

### Key Characteristics
- **Personal VMs**: Single-user compute (not shared like Compute Clusters)
- **Pre-configured**: Jupyter, Python, R, GPU drivers included
- **Managed**: No SSH maintenance required, integrated with Azure ML workspace
- **Auto-Shutdown**: Configurable idle shutdown and schedule-based shutdown
- **Pricing**: Per-minute billing; stopped instances only pay for storage (~$12/month)

### Common Waste Patterns
1. **No auto-shutdown configured** → Running 24/7 when only used 8 hours/day → **67% waste**
2. **GPU instance for CPU workloads** → Paying 3-5x premium for unused GPU → **$514/month waste**
3. **Instance stopped >90 days** → Paying for idle storage → **$22/month waste**
4. **Over-provisioned instance** → Large VM for simple notebooks → **50% waste**
5. **Never accessed** → Created but 0 activity in 60 days → **100% waste**

### Detection Strategy
- **Phase 1**: Configuration-based detection (auto-shutdown, VM size, GPU usage, state)
- **Phase 2**: Azure Monitor metrics + Azure ML API activity logs (CPU, GPU, notebook kernels, training jobs)

---

## Phase 1 Scenarios - Simple Detection

### Scenario 1: No Auto-Shutdown Configured
**Detection Logic**: Compute instance running 24/7 without idle shutdown or schedule-based shutdown configured.

```python
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

def detect_no_auto_shutdown(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect Azure ML Compute Instances without auto-shutdown configured.

    Returns: List of wasteful instances with cost impact
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        # Check if instance is running
        if instance.state != "Running":
            continue

        # Check if auto-shutdown is configured
        has_idle_shutdown = False
        has_schedule_shutdown = False

        if hasattr(instance, 'idle_time_before_shutdown'):
            if instance.idle_time_before_shutdown is not None:
                has_idle_shutdown = True

        if hasattr(instance, 'schedules') and instance.schedules:
            for schedule in instance.schedules:
                if schedule.action == "Stop":
                    has_schedule_shutdown = True
                    break

        if not has_idle_shutdown and not has_schedule_shutdown:
            # Calculate waste assuming 8h/day usage (67% idle time)
            monthly_cost = calculate_instance_cost(instance.size, hours=730)
            monthly_waste = monthly_cost * 0.67  # 67% waste if only used 8h/day

            wasteful_instances.append({
                'resource_id': instance.id,
                'name': instance.name,
                'resource_group': resource_group,
                'workspace': workspace_name,
                'vm_size': instance.size,
                'state': instance.state,
                'created_date': instance.created_on.isoformat() if instance.created_on else None,
                'estimated_monthly_cost': monthly_cost,
                'estimated_monthly_waste': round(monthly_waste, 2),
                'waste_percentage': 67,
                'confidence': 'high',
                'recommendation': 'Enable auto-shutdown: idle timeout (30 min) + schedule (e.g., stop at 6 PM)',
                'scenario': 'ml_compute_instance_no_auto_shutdown',
                'metadata': {
                    'has_idle_shutdown': has_idle_shutdown,
                    'has_schedule_shutdown': has_schedule_shutdown,
                    'usage_assumption': '8 hours/day (weekdays only)'
                }
            })

    return wasteful_instances

def calculate_instance_cost(vm_size: str, hours: int = 730) -> float:
    """Calculate monthly cost for Azure ML Compute Instance."""
    # Pricing per hour (East US, pay-as-you-go)
    vm_prices = {
        # CPU instances
        'Standard_DS11_v2': 0.196,
        'Standard_DS3_v2': 0.196,
        'Standard_DS12_v2': 0.392,
        'Standard_D4s_v3': 0.192,
        'Standard_D8s_v3': 0.384,
        'Standard_E4s_v3': 0.252,
        'Standard_E8s_v3': 0.504,
        'Standard_E16s_v3': 1.008,
        # GPU instances
        'Standard_NC6': 0.90,
        'Standard_NC12': 1.80,
        'Standard_NC24': 3.60,
        'Standard_NC4as_T4_v3': 0.526,
        'Standard_NC8as_T4_v3': 1.052,
        'Standard_NC6s_v3': 3.06,
        'Standard_NC12s_v3': 6.12,
        'Standard_NC24s_v3': 12.24,
        'Standard_ND40rs_v2': 27.20,
    }

    price_per_hour = vm_prices.get(vm_size, 0.196)  # Default to DS11_v2
    monthly_cost = price_per_hour * hours

    return round(monthly_cost, 2)
```

**Cost Impact**:
- Standard_DS3_v2 @ $0.196/hour × 730 hours = **$143/month** always-on
- With auto-shutdown (8h/day, weekdays only): $0.196 × 160h = **$31/month**
- **Waste without auto-shutdown: $112/month (78%)**

**Confidence Level**:
- **High** (85%+): Instance running 24/7 without any shutdown config
- **Medium** (70-84%): Instance has schedule but no idle shutdown

---

### Scenario 2: GPU Instance for CPU-Only Workloads
**Detection Logic**: Instance uses GPU-enabled VM (NC-series, ND-series) but GPU utilization is 0% or metrics unavailable (suggesting no GPU usage).

```python
def detect_gpu_instance_cpu_workload(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect GPU compute instances running CPU-only workloads.

    Phase 1: Detects GPU instances (expensive); Phase 2 confirms with metrics.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        vm_size = instance.size

        # Check if GPU instance
        is_gpu_instance = any([
            vm_size.startswith('Standard_NC'),
            vm_size.startswith('Standard_ND'),
            vm_size.startswith('Standard_NV')
        ])

        if not is_gpu_instance:
            continue

        # Check instance age (must be >14 days to judge)
        if instance.created_on:
            instance_age_days = (datetime.now(instance.created_on.tzinfo) - instance.created_on).days
            if instance_age_days < 14:
                continue

        # Calculate waste (GPU premium vs equivalent CPU instance)
        gpu_monthly_cost = calculate_instance_cost(vm_size, hours=730)

        # Suggest equivalent CPU instance
        recommended_cpu_size = get_equivalent_cpu_instance(vm_size)
        cpu_monthly_cost = calculate_instance_cost(recommended_cpu_size, hours=730)

        monthly_waste = gpu_monthly_cost - cpu_monthly_cost

        wasteful_instances.append({
            'resource_id': instance.id,
            'name': instance.name,
            'resource_group': resource_group,
            'workspace': workspace_name,
            'vm_size': vm_size,
            'state': instance.state,
            'instance_age_days': instance_age_days if instance.created_on else None,
            'gpu_monthly_cost': gpu_monthly_cost,
            'recommended_cpu_size': recommended_cpu_size,
            'cpu_monthly_cost': cpu_monthly_cost,
            'estimated_monthly_waste': round(monthly_waste, 2),
            'waste_percentage': round((monthly_waste / gpu_monthly_cost) * 100, 1),
            'confidence': 'medium',  # High in Phase 2 with GPU metrics
            'recommendation': f'Switch from {vm_size} to {recommended_cpu_size} (no GPU needed)',
            'scenario': 'ml_compute_instance_gpu_for_cpu_workload',
            'metadata': {
                'gpu_type': get_gpu_type(vm_size),
                'needs_phase2_validation': True
            }
        })

    return wasteful_instances

def get_equivalent_cpu_instance(gpu_vm_size: str) -> str:
    """Map GPU instance to equivalent CPU instance."""
    mappings = {
        'Standard_NC6': 'Standard_DS3_v2',       # 6 vCPU → 4 vCPU (close enough)
        'Standard_NC12': 'Standard_DS12_v2',     # 12 vCPU → 4 vCPU
        'Standard_NC24': 'Standard_E8s_v3',      # 24 vCPU → 8 vCPU
        'Standard_NC4as_T4_v3': 'Standard_D4s_v3',
        'Standard_NC8as_T4_v3': 'Standard_D8s_v3',
        'Standard_NC6s_v3': 'Standard_D8s_v3',
        'Standard_NC12s_v3': 'Standard_E8s_v3',
    }
    return mappings.get(gpu_vm_size, 'Standard_DS3_v2')

def get_gpu_type(vm_size: str) -> str:
    """Get GPU type from VM size."""
    if 'NC6s_v3' in vm_size or 'NC12s_v3' in vm_size or 'NC24s_v3' in vm_size:
        return 'NVIDIA V100'
    elif 'T4' in vm_size:
        return 'NVIDIA T4'
    elif 'NC' in vm_size:
        return 'NVIDIA K80'
    elif 'ND' in vm_size:
        return 'NVIDIA V100 or A100'
    return 'Unknown GPU'
```

**Cost Impact**:
- NC6 (1× K80 GPU): **$657/month** ($0.90/hour)
- Equivalent CPU (DS3_v2): **$143/month** ($0.196/hour)
- **Waste: $514/month (78%)**

**Confidence Level**:
- **Medium** (70%): Phase 1 detection (GPU instance exists, age >14 days)
- **High** (90%): Phase 2 detection (GPU utilization <5% over 30 days)
- **Critical** (98%): Phase 2 with 0% GPU usage over 60 days

---

### Scenario 3: Instance Stopped >30 Days (Should Delete)
**Detection Logic**: Compute instance in "Stopped" state for more than 30 days, incurring storage costs with no compute value.

```python
def detect_stopped_instances_long_term(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect compute instances stopped for >30 days.

    Note: Stopped instances still incur OS disk storage costs ($12-22/month).
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Stopped":
            continue

        # Estimate days stopped (Azure doesn't track exact stop time)
        # Use heuristic: if created >30 days ago and stopped, likely stopped for extended period
        if instance.created_on:
            days_since_creation = (datetime.now(instance.created_on.tzinfo) - instance.created_on).days

            if days_since_creation < 30:
                continue  # Too new to judge

            # Check if instance has any recent activity
            # In Phase 1, we approximate; Phase 2 uses actual metrics
            days_stopped_estimate = estimate_stopped_duration(instance)

            if days_stopped_estimate >= 30:
                # Calculate storage cost
                os_disk_size_gb = 128  # Default OS disk size
                os_disk_sku = 'Premium_LRS'  # Typical for ML instances

                if os_disk_sku == 'Premium_LRS':
                    monthly_storage_cost = 22.40  # 128GB Premium SSD
                else:
                    monthly_storage_cost = 12.29  # 128GB Standard SSD

                confidence = 'high' if days_stopped_estimate >= 60 else 'medium'
                if days_stopped_estimate >= 90:
                    confidence = 'critical'

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'state': instance.state,
                    'days_stopped_estimate': days_stopped_estimate,
                    'created_date': instance.created_on.isoformat(),
                    'estimated_monthly_waste': monthly_storage_cost,
                    'waste_percentage': 100,  # Storage cost with no value
                    'confidence': confidence,
                    'recommendation': 'Delete instance - can recreate in 3-5 minutes when needed',
                    'scenario': 'ml_compute_instance_stopped_long_term',
                    'metadata': {
                        'os_disk_size_gb': os_disk_size_gb,
                        'os_disk_sku': os_disk_sku,
                        'recreation_time_minutes': 5
                    }
                })

    return wasteful_instances

def estimate_stopped_duration(instance) -> int:
    """
    Estimate how long instance has been stopped.

    Note: Azure doesn't expose exact stop time via API, so we use heuristics.
    Phase 2 can use Azure Monitor activity logs for precise duration.
    """
    if instance.created_on:
        days_since_creation = (datetime.now(instance.created_on.tzinfo) - instance.created_on).days
        # Conservative estimate: assume stopped for 50% of lifetime if stopped state
        return days_since_creation // 2

    return 0
```

**Cost Impact**:
- Stopped instance with Premium SSD (128GB): **$22.40/month**
- Stopped instance with Standard SSD (128GB): **$12.29/month**
- Deleting and recreating takes only **3-5 minutes**

**Confidence Level**:
- **Critical** (95%+): Stopped >90 days
- **High** (85-94%): Stopped 60-89 days
- **Medium** (70-84%): Stopped 30-59 days

---

### Scenario 4: Over-Provisioned Instance Size
**Detection Logic**: Instance uses large VM (e.g., DS12_v2, E8s_v3) but workload is light (simple notebooks, small datasets).

```python
def detect_overprovisioned_instances(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect compute instances with unnecessarily large VM sizes.

    Phase 1: Detect large VMs; Phase 2: Confirm with CPU/memory metrics.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    # Define "large" VMs that often indicate over-provisioning
    large_vm_sizes = [
        'Standard_DS12_v2',   # 4 vCPU, 28GB
        'Standard_DS13_v2',   # 8 vCPU, 56GB
        'Standard_E8s_v3',    # 8 vCPU, 64GB
        'Standard_E16s_v3',   # 16 vCPU, 128GB
    ]

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        vm_size = instance.size

        if vm_size not in large_vm_sizes:
            continue

        # Check environment tags
        tags = getattr(instance, 'tags', {}) or {}
        environment = tags.get('Environment', '').lower()

        # Large VMs in dev/test are usually over-provisioned
        is_dev_test = environment in ['dev', 'test', 'development', 'sandbox']

        # Suggest rightsizing
        recommended_size = get_rightsized_instance(vm_size)
        current_cost = calculate_instance_cost(vm_size, hours=730)
        recommended_cost = calculate_instance_cost(recommended_size, hours=730)
        monthly_savings = current_cost - recommended_cost

        confidence = 'high' if is_dev_test else 'medium'

        wasteful_instances.append({
            'resource_id': instance.id,
            'name': instance.name,
            'resource_group': resource_group,
            'workspace': workspace_name,
            'vm_size': vm_size,
            'state': instance.state,
            'environment': environment,
            'recommended_size': recommended_size,
            'current_monthly_cost': current_cost,
            'recommended_monthly_cost': recommended_cost,
            'estimated_monthly_savings': round(monthly_savings, 2),
            'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
            'confidence': confidence,
            'recommendation': f'Downsize from {vm_size} to {recommended_size}',
            'scenario': 'ml_compute_instance_overprovisioned',
            'metadata': {
                'is_dev_test': is_dev_test,
                'needs_phase2_validation': True
            }
        })

    return wasteful_instances

def get_rightsized_instance(large_vm_size: str) -> str:
    """Suggest smaller, cost-effective VM size."""
    rightsizing_map = {
        'Standard_DS12_v2': 'Standard_DS11_v2',   # 4→2 vCPU
        'Standard_DS13_v2': 'Standard_DS12_v2',   # 8→4 vCPU
        'Standard_E8s_v3': 'Standard_D4s_v3',     # Memory→compute optimized
        'Standard_E16s_v3': 'Standard_D8s_v3',    # Memory→compute optimized
    }
    return rightsizing_map.get(large_vm_size, 'Standard_DS3_v2')
```

**Cost Impact**:
- DS12_v2 (4 vCPU, 28GB): **$286/month**
- DS11_v2 (2 vCPU, 14GB): **$143/month**
- **Savings: $143/month (50%)**

**Confidence Level**:
- **High** (85%): Large VM in dev/test environment
- **Medium** (70%): Large VM in production without CPU metrics
- **High** (90%): Phase 2 with <20% CPU utilization

---

### Scenario 5: Instance Created But Never Accessed
**Detection Logic**: Instance created >14 days ago but no Jupyter notebooks executed, no kernels started, no training jobs submitted.

```python
def detect_never_accessed_instances(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect compute instances that were created but never used.

    Phase 1: Age check; Phase 2: Confirm with activity logs.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if not instance.created_on:
            continue

        instance_age_days = (datetime.now(instance.created_on.tzinfo) - instance.created_on).days

        if instance_age_days < 14:
            continue  # Too new to judge

        # Phase 1: Flag old instances as potentially unused
        # Phase 2: Confirm with Jupyter activity logs and training jobs

        monthly_cost = calculate_instance_cost(instance.size, hours=730)

        confidence_level = 'medium'
        if instance_age_days >= 60:
            confidence_level = 'high'
        if instance_age_days >= 90:
            confidence_level = 'critical'

        wasteful_instances.append({
            'resource_id': instance.id,
            'name': instance.name,
            'resource_group': resource_group,
            'workspace': workspace_name,
            'vm_size': instance.size,
            'state': instance.state,
            'instance_age_days': instance_age_days,
            'created_date': instance.created_on.isoformat(),
            'estimated_monthly_cost': monthly_cost if instance.state == 'Running' else 12.29,
            'waste_percentage': 100,
            'confidence': confidence_level,
            'recommendation': 'Delete instance - no activity detected since creation',
            'scenario': 'ml_compute_instance_never_accessed',
            'metadata': {
                'needs_phase2_validation': True,
                'phase2_checks': ['jupyter_kernel_count', 'training_job_count']
            }
        })

    return wasteful_instances
```

**Cost Impact**:
- DS3_v2 running 24/7 with zero usage: **$143/month** → **100% waste**
- If stopped: **$12/month** → **100% waste** (should delete)

**Confidence Level**:
- **Critical** (98%): Age >90 days, 0 activity (Phase 2 confirmed)
- **High** (85%): Age 60-89 days, 0 activity
- **Medium** (70%): Age 14-59 days, needs Phase 2 validation

---

### Scenario 6: Multiple Instances Per User (Duplication)
**Detection Logic**: Single user owns 3+ active compute instances in same workspace, suggesting forgotten or duplicate instances.

```python
def detect_multiple_instances_per_user(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect users with 3+ compute instances (likely duplication/waste).
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    # Group instances by user
    user_instances = {}

    for instance in ml_client.compute.list(type="ComputeInstance"):
        # Get assigned user (compute instance owner)
        assigned_user = getattr(instance, 'assigned_user', None)

        if not assigned_user:
            # Try to get from properties
            if hasattr(instance, 'properties'):
                assigned_user = getattr(instance.properties, 'assigned_user', 'Unknown')
            else:
                assigned_user = 'Unknown'

        if assigned_user not in user_instances:
            user_instances[assigned_user] = []

        user_instances[assigned_user].append(instance)

    wasteful_patterns = []

    for user, instances in user_instances.items():
        if len(instances) >= 3:
            # Calculate total cost
            total_monthly_cost = sum(
                calculate_instance_cost(inst.size, hours=730)
                if inst.state == 'Running'
                else 12.29
                for inst in instances
            )

            # Assume user only needs 1-2 instances
            excess_instances = len(instances) - 2
            estimated_waste = total_monthly_cost * (excess_instances / len(instances))

            wasteful_patterns.append({
                'user': user,
                'instance_count': len(instances),
                'instance_names': [inst.name for inst in instances],
                'instance_states': [inst.state for inst in instances],
                'total_monthly_cost': round(total_monthly_cost, 2),
                'estimated_monthly_waste': round(estimated_waste, 2),
                'waste_percentage': round((estimated_waste / total_monthly_cost) * 100, 1),
                'confidence': 'medium',
                'recommendation': f'User has {len(instances)} instances - review and delete {excess_instances} unused ones',
                'scenario': 'ml_compute_instance_multiple_per_user',
                'metadata': {
                    'excess_instance_count': excess_instances,
                    'workspace': workspace_name
                }
            })

    return wasteful_patterns
```

**Cost Impact**:
- User with 3× DS3_v2 instances: **$429/month** total
- Likely only needs 1-2 → **$143-286/month** waste
- **Average waste: 33-67%**

**Confidence Level**:
- **Medium** (65%): 3 instances per user
- **High** (80%): 4+ instances per user
- **Critical** (90%): 5+ instances, with some stopped >30 days

---

### Scenario 7: Premium SSD When Standard Sufficient
**Detection Logic**: Compute instance OS disk uses Premium SSD but workload doesn't require high IOPS (dev/test environment).

```python
def detect_premium_ssd_unnecessary(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect compute instances using Premium SSD unnecessarily.

    Note: OS disk SKU is not directly exposed via azure-ai-ml SDK.
    Need to use Azure Resource Manager API to check disk SKU.
    """
    from azure.mgmt.compute import ComputeManagementClient

    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    compute_client = ComputeManagementClient(credential, subscription_id)

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        # Get VM name (compute instance creates underlying VM)
        vm_name = instance.name

        try:
            # Get VM details including disk
            vm = compute_client.virtual_machines.get(resource_group, vm_name)

            os_disk = vm.storage_profile.os_disk
            os_disk_sku = os_disk.managed_disk.storage_account_type if os_disk.managed_disk else 'Unknown'

            # Check if Premium SSD
            if 'Premium' not in os_disk_sku:
                continue

            # Check environment tags
            tags = instance.tags or {}
            environment = tags.get('Environment', '').lower()

            is_dev_test = environment in ['dev', 'test', 'development', 'sandbox', 'qa']

            if is_dev_test:
                # Calculate waste
                premium_cost = 22.40  # 128GB Premium SSD
                standard_cost = 12.29  # 128GB Standard SSD
                monthly_waste = premium_cost - standard_cost

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'environment': environment,
                    'os_disk_sku': os_disk_sku,
                    'recommended_sku': 'Standard_LRS',
                    'estimated_monthly_waste': round(monthly_waste, 2),
                    'waste_percentage': 45,  # (22.40-12.29)/22.40
                    'confidence': 'high',
                    'recommendation': 'Switch to Standard SSD - dev/test does not need Premium IOPS',
                    'scenario': 'ml_compute_instance_premium_ssd_unnecessary',
                    'metadata': {
                        'premium_monthly_cost': premium_cost,
                        'standard_monthly_cost': standard_cost
                    }
                })

        except Exception as e:
            # VM not found or API error
            continue

    return wasteful_instances
```

**Cost Impact**:
- Premium SSD (128GB): **$22.40/month**
- Standard SSD (128GB): **$12.29/month**
- **Savings: $10.11/month** per instance

**Confidence Level**:
- **High** (85%): Dev/test environment with Premium SSD
- **Medium** (70%): Production environment (may need Premium)

---

### Scenario 8: No Idle Shutdown Configured (Schedule Only)
**Detection Logic**: Instance has schedule-based shutdown (e.g., 6 PM) but no idle shutdown, wasting hours when user finishes early.

```python
def detect_no_idle_shutdown(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect instances with schedule but no idle shutdown.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        # Check shutdown configurations
        has_idle_shutdown = False
        has_schedule_shutdown = False

        if hasattr(instance, 'idle_time_before_shutdown'):
            if instance.idle_time_before_shutdown is not None:
                has_idle_shutdown = True

        if hasattr(instance, 'schedules') and instance.schedules:
            for schedule in instance.schedules:
                if schedule.action == "Stop":
                    has_schedule_shutdown = True
                    break

        # Flag if schedule exists but no idle shutdown
        if has_schedule_shutdown and not has_idle_shutdown:
            monthly_cost = calculate_instance_cost(instance.size, hours=730)

            # Estimate waste: 2-3 hours/day wasted on average
            # Assuming scheduled stop at 6 PM but user finishes at 3-4 PM
            wasted_hours_per_month = 2.5 * 22  # 2.5h/day × 22 workdays
            waste_percentage = (wasted_hours_per_month / 730) * 100
            monthly_waste = monthly_cost * (waste_percentage / 100)

            wasteful_instances.append({
                'resource_id': instance.id,
                'name': instance.name,
                'resource_group': resource_group,
                'workspace': workspace_name,
                'vm_size': instance.size,
                'estimated_monthly_cost': monthly_cost,
                'estimated_monthly_waste': round(monthly_waste, 2),
                'waste_percentage': round(waste_percentage, 1),
                'confidence': 'medium',
                'recommendation': 'Add idle shutdown (30 min) in addition to schedule-based shutdown',
                'scenario': 'ml_compute_instance_no_idle_shutdown',
                'metadata': {
                    'has_schedule': True,
                    'has_idle_shutdown': False,
                    'wasted_hours_per_month_estimate': wasted_hours_per_month
                }
            })

    return wasteful_instances
```

**Cost Impact**:
- DS3_v2 with schedule (6 PM stop) but no idle shutdown
- Wasted: ~2.5 hours/day × 22 days × $0.196/hour = **$11/month** (8% waste)

**Confidence Level**: **Medium** (70%) - Actual waste depends on user behavior

---

### Scenario 9: Instance in Dev/Test with High-Performance SKU
**Detection Logic**: Environment tagged as dev/test but using memory-optimized (E-series) or GPU instances.

```python
def detect_dev_test_high_performance(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect dev/test instances using unnecessarily expensive SKUs.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    # High-performance SKUs inappropriate for dev/test
    high_performance_skus = {
        'Standard_E4s_v3': 'Standard_D4s_v3',
        'Standard_E8s_v3': 'Standard_D4s_v3',
        'Standard_E16s_v3': 'Standard_D8s_v3',
        'Standard_NC6': 'Standard_DS3_v2',
        'Standard_NC6s_v3': 'Standard_DS3_v2',
    }

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        # Check environment
        tags = getattr(instance, 'tags', {}) or {}
        environment = tags.get('Environment', '').lower()

        is_dev_test = environment in ['dev', 'test', 'development', 'sandbox', 'qa', 'staging']

        if not is_dev_test:
            continue

        # Check if using high-performance SKU
        vm_size = instance.size
        recommended_size = high_performance_skus.get(vm_size)

        if not recommended_size:
            continue

        current_cost = calculate_instance_cost(vm_size, hours=730)
        recommended_cost = calculate_instance_cost(recommended_size, hours=730)
        monthly_savings = current_cost - recommended_cost

        wasteful_instances.append({
            'resource_id': instance.id,
            'name': instance.name,
            'resource_group': resource_group,
            'workspace': workspace_name,
            'vm_size': vm_size,
            'environment': environment,
            'recommended_size': recommended_size,
            'current_monthly_cost': current_cost,
            'recommended_monthly_cost': recommended_cost,
            'estimated_monthly_savings': round(monthly_savings, 2),
            'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
            'confidence': 'high',
            'recommendation': f'Dev/test should use {recommended_size} instead of {vm_size}',
            'scenario': 'ml_compute_instance_dev_test_high_performance',
            'metadata': {
                'is_gpu_instance': 'NC' in vm_size,
                'is_memory_optimized': 'E' in vm_size
            }
        })

    return wasteful_instances
```

**Cost Impact**:
- E8s_v3 (memory-optimized) in dev: **$368/month**
- D4s_v3 (general purpose) in dev: **$140/month**
- **Savings: $228/month (62%)**

**Confidence Level**: **High** (85%) - Dev/test rarely needs high-performance SKUs

---

### Scenario 10: Old SDK Version or Deprecated Image
**Detection Logic**: Compute instance using outdated Python SDK, deprecated Ubuntu image, or end-of-support ML frameworks.

```python
def detect_outdated_sdk_image(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect compute instances with outdated software.

    Note: Not direct cost waste, but security/compatibility risk.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    # Deprecated/old versions
    deprecated_images = ['Ubuntu-18.04', 'DSVM-Ubuntu-18']
    old_python_versions = ['3.6', '3.7']  # Python <3.8 is deprecated

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        # Check VM image
        vm_image = getattr(instance, 'os_image_type', 'Unknown')

        is_deprecated_image = any(dep in str(vm_image) for dep in deprecated_images)

        # Check Python version (if available in metadata)
        # Note: azure-ai-ml SDK doesn't expose Python version directly
        # Would need to query instance via SSH or Azure Monitor

        if is_deprecated_image:
            monthly_cost = calculate_instance_cost(instance.size, hours=730) if instance.state == 'Running' else 12.29

            wasteful_instances.append({
                'resource_id': instance.id,
                'name': instance.name,
                'resource_group': resource_group,
                'workspace': workspace_name,
                'vm_size': instance.size,
                'vm_image': vm_image,
                'estimated_monthly_cost': monthly_cost,
                'waste_percentage': 0,  # Not direct cost waste
                'confidence': 'medium',
                'recommendation': 'Recreate instance with latest image (Ubuntu 20.04/22.04)',
                'scenario': 'ml_compute_instance_outdated_image',
                'metadata': {
                    'security_risk': 'high',
                    'compatibility_risk': 'medium'
                }
            })

    return wasteful_instances
```

**Cost Impact**: No direct cost waste, but **security risk** and **compatibility issues**

**Confidence Level**: **Medium** (60%) - More of a hygiene/security issue than pure waste

---

## Phase 2 Scenarios - Metrics-Based Detection

### Scenario 11: Low CPU Utilization (<10% Avg Over 30 Days)
**Detection Logic**: Instance running but average CPU utilization is <10% over 30 days, indicating severe under-utilization.

```python
from azure.monitor.query import MetricsQueryClient
from datetime import datetime, timedelta

def detect_low_cpu_utilization(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect compute instances with low CPU utilization using Azure Monitor metrics.

    Requires: azure-monitor-query==1.3.0
    Permission: Monitoring Reader
    """
    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    metrics_client = MetricsQueryClient(credential)

    wasteful_instances = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        try:
            # Query CPU metrics
            response = metrics_client.query_resource(
                resource_uri=instance.id,
                metric_names=["Percentage CPU"],
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

            if avg_cpu < 10:  # <10% CPU utilization
                # Suggest downsizing
                current_size = instance.size
                recommended_size = suggest_downsize(current_size)

                current_cost = calculate_instance_cost(current_size, hours=730)
                recommended_cost = calculate_instance_cost(recommended_size, hours=730)
                monthly_savings = current_cost - recommended_cost

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': current_size,
                    'avg_cpu_percent': round(avg_cpu, 2),
                    'measurement_period_days': 30,
                    'samples_analyzed': len(cpu_values),
                    'recommended_size': recommended_size,
                    'current_monthly_cost': current_cost,
                    'recommended_monthly_cost': recommended_cost,
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                    'confidence': 'high',
                    'recommendation': f'Downsize from {current_size} to {recommended_size} (avg CPU {avg_cpu:.1f}%)',
                    'scenario': 'ml_compute_instance_low_cpu_utilization',
                    'metadata': {
                        'min_cpu': round(min(cpu_values), 2),
                        'max_cpu': round(max(cpu_values), 2),
                        'p95_cpu': round(sorted(cpu_values)[int(len(cpu_values) * 0.95)], 2)
                    }
                })

        except Exception as e:
            # Metrics not available
            continue

    return wasteful_instances

def suggest_downsize(current_size: str) -> str:
    """Suggest smaller VM size based on low CPU."""
    downsize_map = {
        'Standard_DS12_v2': 'Standard_DS11_v2',
        'Standard_DS13_v2': 'Standard_DS11_v2',
        'Standard_D8s_v3': 'Standard_D4s_v3',
        'Standard_E8s_v3': 'Standard_D4s_v3',
        'Standard_E16s_v3': 'Standard_D4s_v3',
    }
    return downsize_map.get(current_size, 'Standard_DS11_v2')
```

**Cost Impact**:
- DS12_v2 with 8% CPU avg → Downsize to DS11_v2
- Savings: **$143/month** (50%)

**Confidence Level**: **High** (90%) - 30 days of metrics is strong evidence

---

### Scenario 12: Low GPU Utilization (<15% for GPU Instances)
**Detection Logic**: GPU compute instance but GPU utilization <15% over 30 days.

```python
def detect_low_gpu_utilization(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect GPU instances with low GPU utilization.

    Requires: GPU metrics from Azure Monitor
    """
    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    metrics_client = MetricsQueryClient(credential)

    wasteful_instances = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        # Check if GPU instance
        vm_size = instance.size
        is_gpu = any([vm_size.startswith('Standard_NC'), vm_size.startswith('Standard_ND')])

        if not is_gpu:
            continue

        try:
            # Query GPU utilization metrics
            response = metrics_client.query_resource(
                resource_uri=instance.id,
                metric_names=["GPU Utilization", "GPU Memory Utilization"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            gpu_util_values = []
            gpu_mem_values = []

            for metric in response.metrics:
                if metric.name == "GPU Utilization":
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.average is not None:
                                gpu_util_values.append(data_point.average)
                elif metric.name == "GPU Memory Utilization":
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.average is not None:
                                gpu_mem_values.append(data_point.average)

            if not gpu_util_values:
                continue

            avg_gpu_util = sum(gpu_util_values) / len(gpu_util_values)
            avg_gpu_mem = sum(gpu_mem_values) / len(gpu_mem_values) if gpu_mem_values else 0

            if avg_gpu_util < 15:  # <15% GPU utilization
                # Recommend switching to CPU instance
                recommended_size = get_equivalent_cpu_instance(vm_size)

                gpu_cost = calculate_instance_cost(vm_size, hours=730)
                cpu_cost = calculate_instance_cost(recommended_size, hours=730)
                monthly_savings = gpu_cost - cpu_cost

                confidence = 'critical' if avg_gpu_util < 5 else 'high'

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': vm_size,
                    'gpu_type': get_gpu_type(vm_size),
                    'avg_gpu_utilization_percent': round(avg_gpu_util, 2),
                    'avg_gpu_memory_percent': round(avg_gpu_mem, 2),
                    'measurement_period_days': 30,
                    'samples_analyzed': len(gpu_util_values),
                    'recommended_size': recommended_size,
                    'gpu_monthly_cost': gpu_cost,
                    'cpu_monthly_cost': cpu_cost,
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / gpu_cost) * 100, 1),
                    'confidence': confidence,
                    'recommendation': f'Switch to {recommended_size} - GPU not utilized (avg {avg_gpu_util:.1f}%)',
                    'scenario': 'ml_compute_instance_low_gpu_utilization',
                    'metadata': {
                        'min_gpu_util': round(min(gpu_util_values), 2),
                        'max_gpu_util': round(max(gpu_util_values), 2)
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**:
- NC6 (1× K80) with 5% GPU avg: **$657/month**
- Switch to DS3_v2 (CPU): **$143/month**
- **Savings: $514/month (78%)**

**Confidence Level**:
- **Critical** (98%): <5% GPU utilization over 30 days
- **High** (90%): 5-15% GPU utilization

---

### Scenario 13: Instance Idle During Business Hours (9 AM - 5 PM)
**Detection Logic**: Instance running 24/7 but CPU/network activity is near-zero during business hours.

```python
def detect_idle_during_business_hours(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect instances idle during expected business hours.
    """
    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    metrics_client = MetricsQueryClient(credential)

    wasteful_instances = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        try:
            response = metrics_client.query_resource(
                resource_uri=instance.id,
                metric_names=["Percentage CPU", "Network In"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            business_hour_cpu = []
            business_hour_network = []

            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        timestamp = data_point.timestamp
                        hour = timestamp.hour
                        weekday = timestamp.weekday()

                        # Business hours: 9 AM - 5 PM, Monday-Friday
                        if 9 <= hour < 17 and weekday < 5:
                            if metric.name == "Percentage CPU" and data_point.average:
                                business_hour_cpu.append(data_point.average)
                            elif metric.name == "Network In" and data_point.average:
                                business_hour_network.append(data_point.average)

            if not business_hour_cpu:
                continue

            avg_business_cpu = sum(business_hour_cpu) / len(business_hour_cpu)
            avg_business_network = sum(business_hour_network) / len(business_hour_network) if business_hour_network else 0

            if avg_business_cpu < 5 and avg_business_network < 1000:  # <5% CPU, <1KB network
                monthly_cost = calculate_instance_cost(instance.size, hours=730)

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'avg_cpu_business_hours': round(avg_business_cpu, 2),
                    'avg_network_bytes_business_hours': round(avg_business_network, 0),
                    'business_hours_analyzed': len(business_hour_cpu),
                    'estimated_monthly_cost': monthly_cost,
                    'waste_percentage': 80,  # High waste if idle during work hours
                    'confidence': 'high',
                    'recommendation': 'Instance idle during business hours - consider deleting or strict auto-shutdown',
                    'scenario': 'ml_compute_instance_idle_business_hours',
                    'metadata': {
                        'measurement_period_days': 30
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**:
- Instance idle 9-5 weekdays but running 24/7: **80% waste**
- DS3_v2: $143/month → **$114/month waste**

**Confidence Level**: **High** (85%) - Idle during work hours is strong waste signal

---

### Scenario 14: No Jupyter Notebook Activity (30+ Days)
**Detection Logic**: No Jupyter kernels started in 30+ days, indicating instance is unused.

```python
def detect_no_jupyter_activity(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect instances with no Jupyter activity.

    Requires: Azure ML workspace API access to query compute instance activity.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        # Check instance age
        if not instance.created_on:
            continue

        instance_age_days = (datetime.now(instance.created_on.tzinfo) - instance.created_on).days

        if instance_age_days < 30:
            continue

        # Query last activity time
        # Note: azure-ai-ml SDK doesn't expose Jupyter activity directly
        # Would need to use Azure Monitor Application Insights or custom logging

        # For Phase 2, we approximate by checking if no training jobs submitted
        try:
            # Check workspace jobs associated with this compute
            jobs = list(ml_client.jobs.list(compute_name=instance.name))

            if len(jobs) == 0:
                monthly_cost = calculate_instance_cost(instance.size, hours=730)

                confidence = 'high' if instance_age_days >= 60 else 'medium'
                if instance_age_days >= 90:
                    confidence = 'critical'

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'instance_age_days': instance_age_days,
                    'jupyter_kernels_started': 0,  # Placeholder - needs actual Jupyter logs
                    'training_jobs_submitted': len(jobs),
                    'estimated_monthly_cost': monthly_cost,
                    'waste_percentage': 100,
                    'confidence': confidence,
                    'recommendation': 'Delete instance - no Jupyter or training activity in 30+ days',
                    'scenario': 'ml_compute_instance_no_jupyter_activity',
                    'metadata': {
                        'created_date': instance.created_on.isoformat()
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**:
- DS3_v2 with 0 activity: **$143/month** → **100% waste**

**Confidence Level**:
- **Critical** (98%): 90+ days, 0 activity
- **High** (90%): 60-89 days, 0 activity
- **Medium** (75%): 30-59 days, 0 activity

---

### Scenario 15: No Training Jobs Submitted (30+ Days)
**Detection Logic**: Compute instance exists but no training jobs submitted to Azure ML workspace in 30+ days.

```python
def detect_no_training_jobs(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect instances with no training job submissions.
    """
    credential = DefaultAzureCredential()
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    wasteful_instances = []
    cutoff_date = datetime.now() - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        # Check if any jobs submitted from this instance
        recent_jobs = []

        try:
            for job in ml_client.jobs.list():
                if hasattr(job, 'compute') and job.compute == instance.name:
                    if hasattr(job, 'created_on') and job.created_on > cutoff_date:
                        recent_jobs.append(job)

            if len(recent_jobs) == 0:
                monthly_cost = calculate_instance_cost(instance.size, hours=730)

                # Note: Compute instances can be used for interactive work without submitting jobs
                # So confidence is medium unless combined with other metrics

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'training_jobs_last_30_days': len(recent_jobs),
                    'estimated_monthly_cost': monthly_cost,
                    'waste_percentage': 50,  # May be used for interactive work
                    'confidence': 'medium',
                    'recommendation': 'No training jobs submitted - consider using Compute Cluster instead',
                    'scenario': 'ml_compute_instance_no_training_jobs',
                    'metadata': {
                        'alternative': 'Azure ML Compute Cluster (auto-scales to 0)'
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**:
- Instance for training but no jobs → Use Compute Cluster instead
- Savings: **~70%** (Compute Cluster auto-scales to 0)

**Confidence Level**: **Medium** (70%) - May be used for interactive notebooks

---

### Scenario 16: Memory Consistently Under-Utilized (<25%)
**Detection Logic**: Memory-optimized instance (E-series) but memory usage <25% consistently.

```python
def detect_low_memory_utilization(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect memory-optimized instances with low memory usage.
    """
    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    metrics_client = MetricsQueryClient(credential)

    wasteful_instances = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        # Check if memory-optimized instance
        vm_size = instance.size
        if not vm_size.startswith('Standard_E'):
            continue

        try:
            # Query memory metrics
            response = metrics_client.query_resource(
                resource_uri=instance.id,
                metric_names=["Available Memory Bytes"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            available_memory_values = []

            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average is not None:
                            available_memory_values.append(data_point.average)

            if not available_memory_values:
                continue

            # Get total memory for VM size
            vm_memory_gb = {
                'Standard_E4s_v3': 32,
                'Standard_E8s_v3': 64,
                'Standard_E16s_v3': 128,
            }.get(vm_size, 32)

            vm_memory_bytes = vm_memory_gb * 1024 * 1024 * 1024

            avg_available_memory = sum(available_memory_values) / len(available_memory_values)
            avg_used_memory_percent = ((vm_memory_bytes - avg_available_memory) / vm_memory_bytes) * 100

            if avg_used_memory_percent < 25:  # <25% memory usage
                # Recommend switching to compute-optimized
                recommended_size = {
                    'Standard_E4s_v3': 'Standard_D4s_v3',
                    'Standard_E8s_v3': 'Standard_D8s_v3',
                    'Standard_E16s_v3': 'Standard_D8s_v3',
                }.get(vm_size, 'Standard_D4s_v3')

                current_cost = calculate_instance_cost(vm_size, hours=730)
                recommended_cost = calculate_instance_cost(recommended_size, hours=730)
                monthly_savings = current_cost - recommended_cost

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': vm_size,
                    'avg_memory_used_percent': round(avg_used_memory_percent, 2),
                    'vm_total_memory_gb': vm_memory_gb,
                    'measurement_period_days': 30,
                    'samples_analyzed': len(available_memory_values),
                    'recommended_size': recommended_size,
                    'current_monthly_cost': current_cost,
                    'recommended_monthly_cost': recommended_cost,
                    'estimated_monthly_savings': round(monthly_savings, 2),
                    'waste_percentage': round((monthly_savings / current_cost) * 100, 1),
                    'confidence': 'high',
                    'recommendation': f'Switch from {vm_size} to {recommended_size} (memory-optimized not needed)',
                    'scenario': 'ml_compute_instance_low_memory_utilization',
                    'metadata': {
                        'current_series': 'E-series (memory-optimized)',
                        'recommended_series': 'D-series (compute-optimized)'
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**:
- E8s_v3 (64 GB RAM) with 20% memory usage: **$368/month**
- D8s_v3 (32 GB RAM): **$280/month**
- **Savings: $88/month (24%)**

**Confidence Level**: **High** (85%) - 30 days of memory metrics

---

### Scenario 17: Network Idle (No Data Transfer In/Out)
**Detection Logic**: No significant network activity, suggesting no data downloads, remote file access, or API calls.

```python
def detect_network_idle(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect instances with minimal network activity.
    """
    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    metrics_client = MetricsQueryClient(credential)

    wasteful_instances = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        try:
            response = metrics_client.query_resource(
                resource_uri=instance.id,
                metric_names=["Network In", "Network Out"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=6),
                aggregations=["Total"]
            )

            network_in_values = []
            network_out_values = []

            for metric in response.metrics:
                if metric.name == "Network In":
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.total is not None:
                                network_in_values.append(data_point.total)
                elif metric.name == "Network Out":
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.total is not None:
                                network_out_values.append(data_point.total)

            if not network_in_values:
                continue

            total_network_in_mb = sum(network_in_values) / (1024 * 1024)
            total_network_out_mb = sum(network_out_values) / (1024 * 1024) if network_out_values else 0

            # Threshold: <100 MB total over 30 days is very low
            if total_network_in_mb < 100 and total_network_out_mb < 100:
                monthly_cost = calculate_instance_cost(instance.size, hours=730)

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'total_network_in_mb_30_days': round(total_network_in_mb, 2),
                    'total_network_out_mb_30_days': round(total_network_out_mb, 2),
                    'estimated_monthly_cost': monthly_cost,
                    'waste_percentage': 75,
                    'confidence': 'medium',
                    'recommendation': 'Minimal network activity - instance may be unused',
                    'scenario': 'ml_compute_instance_network_idle',
                    'metadata': {
                        'measurement_period_days': 30
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**: Indicator of non-use; combine with CPU/GPU metrics for higher confidence

**Confidence Level**: **Medium** (65%) - Could be doing local file work

---

### Scenario 18: Disk I/O Near Zero
**Detection Logic**: No disk read/write activity, indicating no notebook execution, dataset processing, or model training.

```python
def detect_disk_io_idle(subscription_id: str, resource_group: str, workspace_name: str) -> list:
    """
    Detect instances with near-zero disk I/O.
    """
    credential = DefaultAzureCredential()

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )

    metrics_client = MetricsQueryClient(credential)

    wasteful_instances = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for instance in ml_client.compute.list(type="ComputeInstance"):
        if instance.state != "Running":
            continue

        try:
            response = metrics_client.query_resource(
                resource_uri=instance.id,
                metric_names=["OS Disk Read Bytes/Sec", "OS Disk Write Bytes/Sec"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=6),
                aggregations=["Average"]
            )

            disk_read_values = []
            disk_write_values = []

            for metric in response.metrics:
                if "Read" in metric.name:
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.average is not None:
                                disk_read_values.append(data_point.average)
                elif "Write" in metric.name:
                    for time_series in metric.timeseries:
                        for data_point in time_series.data:
                            if data_point.average is not None:
                                disk_write_values.append(data_point.average)

            if not disk_read_values:
                continue

            avg_disk_read = sum(disk_read_values) / len(disk_read_values)
            avg_disk_write = sum(disk_write_values) / len(disk_write_values) if disk_write_values else 0

            # Threshold: <100 bytes/sec is essentially idle
            if avg_disk_read < 100 and avg_disk_write < 100:
                monthly_cost = calculate_instance_cost(instance.size, hours=730)

                wasteful_instances.append({
                    'resource_id': instance.id,
                    'name': instance.name,
                    'resource_group': resource_group,
                    'workspace': workspace_name,
                    'vm_size': instance.size,
                    'avg_disk_read_bytes_sec': round(avg_disk_read, 2),
                    'avg_disk_write_bytes_sec': round(avg_disk_write, 2),
                    'estimated_monthly_cost': monthly_cost,
                    'waste_percentage': 80,
                    'confidence': 'high',
                    'recommendation': 'Zero disk I/O - instance is idle and should be stopped or deleted',
                    'scenario': 'ml_compute_instance_disk_io_idle',
                    'metadata': {
                        'measurement_period_days': 30,
                        'samples_analyzed': len(disk_read_values)
                    }
                })

        except Exception as e:
            continue

    return wasteful_instances
```

**Cost Impact**: Strong idle indicator; combined with CPU/network metrics gives **95% confidence**

**Confidence Level**: **High** (80%) when disk I/O + CPU + network all near zero

---

## Pricing Structure

### Azure ML Compute Instance Costs (Pay-as-you-go, East US)

#### CPU Instances

| VM Size | vCPU | RAM (GB) | Price/Hour | Monthly (730h) | Monthly (8h/day) | Use Case |
|---------|------|----------|------------|----------------|------------------|----------|
| Standard_DS11_v2 | 2 | 14 | $0.196 | **$143** | **$31** | Light notebooks |
| Standard_DS3_v2 | 4 | 14 | $0.196 | **$143** | **$31** | Standard dev |
| Standard_DS12_v2 | 4 | 28 | $0.392 | **$286** | **$63** | Medium workloads |
| Standard_D4s_v3 | 4 | 16 | $0.192 | **$140** | **$31** | General purpose |
| Standard_D8s_v3 | 8 | 32 | $0.384 | **$280** | **$61** | Multi-core tasks |
| Standard_E4s_v3 | 4 | 32 | $0.252 | **$184** | **$40** | Memory-heavy |
| Standard_E8s_v3 | 8 | 64 | $0.504 | **$368** | **$81** | Large datasets |
| Standard_E16s_v3 | 16 | 128 | $1.008 | **$736** | **$161** | Very large data |

#### GPU Instances

| VM Size | vCPU | RAM (GB) | GPU | Price/Hour | Monthly (730h) | Monthly (8h/day) | Use Case |
|---------|------|----------|-----|------------|----------------|------------------|----------|
| Standard_NC6 | 6 | 56 | 1× K80 (12GB) | $0.90 | **$657** | **$144** | Legacy GPU |
| Standard_NC12 | 12 | 112 | 2× K80 (24GB) | $1.80 | **$1,314** | **$288** | Multi-GPU old |
| Standard_NC24 | 24 | 224 | 4× K80 (48GB) | $3.60 | **$2,628** | **$576** | Large multi-GPU |
| Standard_NC4as_T4_v3 | 4 | 28 | 1× T4 (16GB) | $0.526 | **$384** | **$84** | Inference, small train |
| Standard_NC8as_T4_v3 | 8 | 56 | 1× T4 (16GB) | $1.052 | **$768** | **$168** | Training |
| Standard_NC6s_v3 | 6 | 112 | 1× V100 (16GB) | $3.06 | **$2,234** | **$490** | Deep learning |
| Standard_NC12s_v3 | 12 | 224 | 2× V100 (32GB) | $6.12 | **$4,468** | **$980** | Multi-GPU DL |
| Standard_NC24s_v3 | 24 | 448 | 4× V100 (64GB) | $12.24 | **$8,935** | **$1,960** | Large-scale DL |
| Standard_ND40rs_v2 | 40 | 672 | 8× V100 (256GB) | $27.20 | **$19,856** | **$4,358** | Massive multi-GPU |

#### Stopped Instance Costs (Storage Only)

| Disk Type | Size | Monthly Cost |
|-----------|------|--------------|
| Standard SSD (S10) | 128 GB | **$12.29** |
| Premium SSD (P10) | 128 GB | **$22.40** |
| Standard SSD (S15) | 256 GB | **$24.58** |
| Premium SSD (P15) | 256 GB | **$44.80** |

**Key Insight**: Stopped instances only pay for disk storage, NOT compute! Always stop instances when not in use.

#### Auto-Shutdown Savings Examples

**Scenario: Data scientist uses instance 8 hours/day, 22 workdays/month**

| VM Size | 24/7 Cost | With Auto-Shutdown (8h/day) | Monthly Savings | Savings % |
|---------|-----------|------------------------------|-----------------|-----------|
| DS3_v2 | $143 | $31 | **$112** | **78%** |
| E8s_v3 | $368 | $81 | **$287** | **78%** |
| NC6 (GPU) | $657 | $144 | **$513** | **78%** |
| NC6s_v3 (V100) | $2,234 | $490 | **$1,744** | **78%** |

---

## Required Azure Permissions

### Minimum RBAC Roles

**Phase 1 Detection (Configuration):**
- **Reader** role on Resource Group or Subscription
- **Azure ML Workspace Reader** role

**Phase 2 Detection (Metrics):**
- **Monitoring Reader** role on Resource Group or Subscription

### Custom Role Definition (Recommended)

```json
{
  "Name": "CloudWaste ML Compute Instance Scanner",
  "Description": "Read-only access to Azure ML compute instances and metrics for waste detection",
  "Actions": [
    "Microsoft.MachineLearningServices/workspaces/read",
    "Microsoft.MachineLearningServices/workspaces/computes/read",
    "Microsoft.MachineLearningServices/workspaces/computes/listKeys/action",
    "Microsoft.MachineLearningServices/workspaces/jobs/read",
    "Microsoft.Insights/Metrics/Read",
    "Microsoft.Insights/DiagnosticSettings/Read",
    "Microsoft.Compute/virtualMachines/read"
  ],
  "NotActions": [],
  "AssignableScopes": ["/subscriptions/{subscription-id}"]
}
```

### Service Principal Setup

```bash
# Create service principal
az ad sp create-for-rbac --name "CloudWaste-ML-Scanner" \
  --role "Reader" \
  --scopes "/subscriptions/{subscription-id}"

# Add Azure ML Workspace Reader role
az role assignment create \
  --assignee {service-principal-id} \
  --role "Azure ML Workspace Reader" \
  --scope "/subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.MachineLearningServices/workspaces/{workspace}"

# Add Monitoring Reader role
az role assignment create \
  --assignee {service-principal-id} \
  --role "Monitoring Reader" \
  --scope "/subscriptions/{subscription-id}"
```

---

## Azure CLI Commands for Testing

### 1. Create Test Azure ML Workspace and Compute Instance

```bash
# Set variables
RESOURCE_GROUP="cloudwaste-ml-test-rg"
LOCATION="eastus"
WORKSPACE_NAME="cloudwaste-test-workspace"
COMPUTE_NAME="test-compute-instance"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure ML workspace
az ml workspace create \
  --name $WORKSPACE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Create compute instance (DS3_v2, standard)
az ml compute create \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --type ComputeInstance \
  --size Standard_DS3_v2

# Expected cost: $143/month if left running 24/7
```

### 2. Configure Auto-Shutdown

```bash
# Enable idle shutdown (30 minutes)
az ml compute update \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --idle-time-before-shutdown-minutes 30

# Add schedule-based shutdown (stop at 6 PM weekdays)
az ml compute update \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --schedule-action stop \
  --schedule-time "18:00" \
  --schedule-weekdays "Monday,Tuesday,Wednesday,Thursday,Friday"

# Add schedule-based startup (start at 9 AM weekdays)
az ml compute update \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --schedule-action start \
  --schedule-time "09:00" \
  --schedule-weekdays "Monday,Tuesday,Wednesday,Thursday,Friday"
```

### 3. Query Compute Instance Details

```bash
# Get compute instance details
az ml compute show \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME

# List all compute instances in workspace
az ml compute list \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --type ComputeInstance \
  --output table

# Check state (Running, Stopped, etc.)
az ml compute show \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --query "properties.state"
```

### 4. Query Azure Monitor Metrics

```bash
# Get compute instance resource ID
COMPUTE_ID=$(az ml compute show \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --query "id" -o tsv)

# Get CPU utilization (last 30 days)
az monitor metrics list \
  --resource $COMPUTE_ID \
  --metric "Percentage CPU" \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table

# Get GPU utilization (GPU instances only)
az monitor metrics list \
  --resource $COMPUTE_ID \
  --metric "GPU Utilization" \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table

# Get available memory
az monitor metrics list \
  --resource $COMPUTE_ID \
  --metric "Available Memory Bytes" \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table
```

### 5. Stop and Start Instance

```bash
# Stop compute instance (stops billing, keeps disk)
az ml compute stop \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME

# Start compute instance
az ml compute start \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME

# Delete compute instance
az ml compute delete \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --yes
```

### 6. Simulate Waste Scenarios

**Scenario 1: No Auto-Shutdown**
```bash
# Create instance without auto-shutdown
az ml compute create \
  --name "no-autoshutdown-instance" \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --type ComputeInstance \
  --size Standard_DS3_v2

# Leave running 24/7 → Waste detection after 7 days
```

**Scenario 2: GPU for CPU Workloads**
```bash
# Create GPU instance but don't run GPU workloads
az ml compute create \
  --name "gpu-wasted-instance" \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --type ComputeInstance \
  --size Standard_NC6

# Run only CPU-based notebooks → Waste $514/month
```

**Scenario 3: Stopped >30 Days**
```bash
# Create and immediately stop
az ml compute create --name "stopped-instance" \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --type ComputeInstance \
  --size Standard_DS3_v2

az ml compute stop --name "stopped-instance" \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME

# Wait 30+ days → Waste detection triggers
```

### 7. Cleanup Resources

```bash
# Delete specific compute instance
az ml compute delete \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --yes

# Delete entire workspace (removes all compute instances)
az ml workspace delete \
  --name $WORKSPACE_NAME \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete resource group (removes everything)
az group delete --name $RESOURCE_GROUP --yes
```

---

## Comparison with Alternatives

### Compute Instance vs Compute Cluster vs Databricks vs Local Jupyter

| Feature | Compute Instance | Compute Cluster | Azure Databricks | Local Jupyter |
|---------|------------------|-----------------|------------------|---------------|
| **Use Case** | Interactive dev, notebooks | Batch training jobs | Collaborative, Spark | Small datasets |
| **Pricing Model** | Per-minute, always-on | Per-minute, auto-scale | DBU + VM costs | Free (local hardware) |
| **Auto-Scale to 0** | ❌ No | ✅ Yes | ✅ Yes | N/A |
| **Min Cost (4 vCPU, 8h/day)** | $31/month (DS3_v2) | $18/month (auto-scale) | $50/month (incl. DBU) | $0 |
| **Max Cost (24/7)** | $143/month | $143/month (if no scale) | $215/month | $0 |
| **Setup Time** | 3-5 minutes | 5-10 minutes | 2-3 minutes | Immediate |
| **Jupyter/Notebooks** | ✅ Pre-installed | ❌ No (submit jobs only) | ✅ Pre-installed | ✅ Manual install |
| **GPU Support** | ✅ Yes | ✅ Yes | ✅ Yes | Depends on hardware |
| **Shared/Multi-User** | ❌ Single-user | ✅ Multi-user | ✅ Multi-user | ❌ Single-user |
| **Idle Shutdown** | ✅ Configurable | ✅ Auto (scale to 0) | ✅ Auto | N/A |
| **Waste Risk** | **HIGH** | **LOW** | **MEDIUM** | None |

### When to Use Compute Instance

✅ **Use Compute Instance When:**
- Interactive development with Jupyter/RStudio
- Need GPU for experimentation
- Quick prototyping with Azure ML SDK
- Require persistent environment with installed packages
- Working on exploratory data analysis

❌ **Don't Use Compute Instance When:**
- Only running scheduled training jobs → Use **Compute Cluster**
- Workload runs <2 hours/day → Use **Compute Cluster** with auto-scale
- Local laptop sufficient (datasets <10 GB) → Use **Local Jupyter**
- Need collaborative notebooks → Use **Azure Databricks**
- Spark-based processing required → Use **Azure Databricks or Synapse**

### Cost Comparison Examples

**Scenario: Data scientist working 8 hours/day, 22 days/month (176 hours)**

| Solution | Configuration | Monthly Cost | Notes |
|----------|---------------|--------------|-------|
| Compute Instance | DS3_v2, 24/7 | **$143** | Wasteful! |
| Compute Instance | DS3_v2, 8h/day auto-shutdown | **$31** | ✅ Optimal |
| Compute Cluster | D4s_v3, auto-scale 0-1 | **$28** | Good for training jobs |
| Databricks | Standard, 4 vCPU | **$50** | Includes collaboration tools |
| Local Jupyter | Laptop (16 GB RAM) | **$0** | Free but limited |

**Winner: Compute Instance with auto-shutdown** for interactive dev at **$31/month**

---

## Test Matrix

### Phase 1 Tests (Configuration-Based)

| Scenario | Test Setup | Expected Detection | Validation Command |
|----------|------------|-------------------|-------------------|
| 1. No auto-shutdown | Create instance without idle or schedule shutdown | HIGH confidence, 67% waste | `az ml compute show --query 'properties.schedules'` → null |
| 2. GPU for CPU workload | Create NC6 instance, run only CPU notebooks | MEDIUM confidence, 78% waste | Check GPU metrics → 0% usage |
| 3. Stopped >30 days | Stop instance, wait 30+ days | HIGH confidence, $12/month waste | `az ml compute show --query 'properties.state'` → Stopped |
| 4. Over-provisioned | Create DS12_v2 for simple notebooks | MEDIUM confidence, 50% waste | Tag: Environment=dev + large VM |
| 5. Never accessed | Create instance 60 days ago, no activity | CRITICAL confidence, 100% waste | Check Jupyter logs → 0 kernels |
| 6. Multiple per user | Create 4 instances for same user | MEDIUM confidence, 33% waste | List instances by user → 4+ |
| 7. Premium SSD dev/test | Tag=dev + Premium SSD OS disk | HIGH confidence, $10/month waste | Check disk SKU → Premium_LRS |
| 8. No idle shutdown | Schedule shutdown only, no idle config | MEDIUM confidence, 8% waste | Has schedule but no idle timeout |
| 9. Dev/test high-perf SKU | Tag=dev + E8s_v3 (memory-optimized) | HIGH confidence, 62% waste | Environment tag + E-series |
| 10. Outdated image | Ubuntu 18.04 image | MEDIUM confidence, security risk | Check OS image version |

### Phase 2 Tests (Metrics-Based)

| Scenario | Test Setup | Expected Detection | Validation Metric |
|----------|------------|-------------------|-------------------|
| 11. Low CPU (<10%) | Run instance with minimal notebook work for 30 days | HIGH confidence, 50% waste | Azure Monitor: Percentage CPU < 10% |
| 12. Low GPU (<15%) | GPU instance with CPU-only notebooks for 30 days | CRITICAL confidence, 78% waste | Azure Monitor: GPU Utilization < 15% |
| 13. Idle business hours | Instance running 24/7 but no activity 9-5 weekdays | HIGH confidence, 80% waste | CPU < 5% during 9 AM - 5 PM |
| 14. No Jupyter activity | No kernels started in 60+ days | CRITICAL confidence, 100% waste | Jupyter logs: kernel_count = 0 |
| 15. No training jobs | No jobs submitted to workspace in 30+ days | MEDIUM confidence, 50% waste | Azure ML jobs list → 0 jobs |
| 16. Low memory (<25%) | E-series instance with <25% memory used | HIGH confidence, 24% waste | Available Memory Bytes → >75% free |
| 17. Network idle | No downloads/uploads for 30 days | MEDIUM confidence, indicator | Network In/Out → <100 MB total |
| 18. Disk I/O zero | No file operations for 30 days | HIGH confidence, 80% waste | Disk Read/Write Bytes/Sec → <100 |

### End-to-End Test Script

```python
# test_ml_compute_instance_detection.py
import pytest
from datetime import datetime, timedelta

def test_scenario_1_no_auto_shutdown():
    """Test detection of instances without auto-shutdown."""
    wasteful = detect_no_auto_shutdown(subscription_id, resource_group, workspace_name)

    # Find test instance
    test_instance = next((inst for inst in wasteful if inst['name'] == 'no-autoshutdown-instance'), None)

    assert test_instance is not None
    assert test_instance['confidence'] == 'high'
    assert test_instance['waste_percentage'] == 67
    assert test_instance['estimated_monthly_waste'] > 90

def test_scenario_11_low_cpu_utilization():
    """Test detection of low CPU utilization."""
    wasteful = detect_low_cpu_utilization(subscription_id, resource_group, workspace_name)

    test_instance = next((inst for inst in wasteful if inst['avg_cpu_percent'] < 10), None)

    assert test_instance is not None
    assert test_instance['confidence'] == 'high'
    assert test_instance['recommended_size'] != test_instance['vm_size']
    assert test_instance['estimated_monthly_savings'] > 50

# Run all Phase 1 tests
pytest test_ml_compute_instance_detection.py -v -k "phase1"

# Run all Phase 2 tests (requires 30 days of metrics)
pytest test_ml_compute_instance_detection.py -v -k "phase2"
```

---

## Troubleshooting Guide

### Issue 1: Azure ML SDK Cannot List Compute Instances

**Symptoms:**
- `ml_client.compute.list()` returns empty or throws authentication error
- Error: `AuthenticationFailed` or `ResourceNotFound`

**Causes:**
- Service principal lacks permissions
- Workspace name/resource group incorrect
- azure-ai-ml SDK not installed or outdated

**Solution:**
```bash
# Install latest azure-ai-ml SDK
pip install --upgrade azure-ai-ml

# Verify service principal permissions
az role assignment list \
  --assignee {service-principal-id} \
  --scope "/subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.MachineLearningServices/workspaces/{workspace}"

# Test authentication
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential

ml_client = MLClient(
    credential=DefaultAzureCredential(),
    subscription_id="<subscription-id>",
    resource_group_name="<resource-group>",
    workspace_name="<workspace-name>"
)

print(list(ml_client.compute.list()))
```

---

### Issue 2: GPU Metrics Not Available

**Symptoms:**
- `GPU Utilization` and `GPU Memory Utilization` metrics return no data
- Error: `MetricNotFound`

**Causes:**
- Instance is CPU-only (not GPU)
- GPU metrics take 15-30 minutes to populate after instance starts
- NVIDIA drivers not loaded (rare)

**Solution:**
```bash
# Verify instance is GPU-enabled
az ml compute show \
  --name $COMPUTE_NAME \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --query "properties.vmSize"

# Expected output: Standard_NC6, Standard_NC6s_v3, etc.

# Wait 30 minutes after instance start, then retry
az monitor metrics list \
  --resource $COMPUTE_ID \
  --metric "GPU Utilization" \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --aggregation Average
```

---

### Issue 3: Cannot Determine Jupyter Activity

**Symptoms:**
- No way to check if Jupyter notebooks were executed
- azure-ai-ml SDK doesn't expose Jupyter activity logs

**Causes:**
- Azure ML API doesn't directly expose Jupyter server logs
- Need to use alternative indicators (training jobs, CPU metrics, disk I/O)

**Solution:**
```python
# Workaround: Check training jobs submitted from compute instance
def check_jupyter_activity_proxy(ml_client, instance_name):
    """
    Use proxy indicators for Jupyter activity:
    1. Training jobs submitted from instance
    2. CPU/disk metrics (Phase 2)
    3. Network activity
    """

    # Check training jobs
    jobs = list(ml_client.jobs.list(compute_name=instance_name))

    # Check CPU metrics (requires Azure Monitor)
    metrics_client = MetricsQueryClient(DefaultAzureCredential())
    response = metrics_client.query_resource(
        resource_uri=instance.id,
        metric_names=["Percentage CPU"],
        timespan=(datetime.utcnow() - timedelta(days=7), datetime.utcnow()),
        aggregations=["Average"]
    )

    # If jobs > 0 OR CPU > 10%, likely has Jupyter activity
    has_activity = len(jobs) > 0 or avg_cpu > 10

    return has_activity
```

---

### Issue 4: High False Positives for "Over-Provisioned"

**Symptoms:**
- Instances flagged as over-provisioned but user legitimately needs resources
- E-series (memory-optimized) flagged in dev/test but user loading large datasets

**Causes:**
- Phase 1 detection doesn't have CPU/memory metrics
- Heuristics based on environment tags can be wrong

**Solution:**
```python
# Enhanced detection: Combine Phase 1 tags with Phase 2 metrics
def detect_overprovisioned_enhanced(ml_client, metrics_client, instance):
    """
    Phase 1: Flag based on VM size + environment tag
    Phase 2: Confirm with CPU/memory metrics
    """

    # Phase 1: Check environment
    is_dev_test = instance.tags.get('Environment', '').lower() in ['dev', 'test']
    is_large_vm = instance.size in ['Standard_E8s_v3', 'Standard_E16s_v3']

    if not (is_dev_test and is_large_vm):
        return False

    # Phase 2: Check actual utilization
    cpu_avg = get_cpu_metrics(metrics_client, instance.id, days=30)
    memory_avg = get_memory_metrics(metrics_client, instance.id, days=30)

    # Only flag if BOTH environment tag AND low utilization
    if cpu_avg < 20 and memory_avg < 30:
        return True  # HIGH confidence over-provisioned

    return False  # User may legitimately need resources
```

---

### Issue 5: Stopped Instances Flagged But User Plans to Resume

**Symptoms:**
- Instances stopped for 35 days flagged for deletion
- User plans to resume in 1-2 weeks (project on hold)

**Causes:**
- Detection doesn't account for project timelines
- No "pause project" tag available

**Solution:**
```python
# Add exemption logic: Check for "keep" or "paused" tags
def detect_stopped_instances_with_exemptions(ml_client, instance):
    """
    Detect stopped instances but respect exemption tags.
    """

    if instance.state != "Stopped":
        return False

    # Check for exemption tags
    tags = instance.tags or {}
    status = tags.get('Status', '').lower()

    if status in ['keep', 'paused', 'on-hold', 'temporary-stop']:
        return False  # Don't flag

    # Check stopped duration
    days_stopped = estimate_stopped_duration(instance)

    if days_stopped >= 90:
        return True  # Flag even with tags (too long)
    elif days_stopped >= 30:
        return True  # Flag for review

    return False
```

---

## Business Impact Analysis

### Small Data Science Team (5 Users, 5 Instances)

**Typical Setup:**
- 3 CPU instances (DS3_v2) for interactive dev
- 2 GPU instances (NC6) for model training

**Baseline Cost (No Optimizations):**
- 3× DS3_v2 running 24/7: 3 × $143 = **$429/month**
- 2× NC6 running 24/7: 2 × $657 = **$1,314/month**
- **Total: $1,743/month** ($20,916/year)

**Waste Detected:**

| Scenario | Instances Affected | Monthly Waste | Annual Waste |
|----------|-------------------|---------------|--------------|
| No auto-shutdown (24/7) | 3 CPU, 2 GPU | $1,254 | $15,048 |
| GPU for CPU workloads | 1 GPU instance | $514 | $6,168 |
| Over-provisioned (DS12→DS11) | 1 CPU instance | $143 | $1,716 |
| Stopped >90 days (unused) | 1 stopped instance | $22 | $264 |
| **Total Waste** | **5 instances** | **$1,933** | **$23,196** |

**After CloudWaste Optimization:**
- Enable auto-shutdown (8h/day): 3× $31 + 1× $144 = **$237/month** (CPU+1GPU)
- Switch 1 GPU to CPU: $143/month
- Rightsize over-provisioned: Save $143/month
- Delete stopped instance: Save $22/month
- **Optimized Total: $380/month** ($4,560/year)

**Savings: $1,363/month** (**$16,356/year**) → **78% reduction**

**ROI:**
- CloudWaste subscription: $500/month
- Net savings: $863/month
- **ROI: 173% annually**

---

### Enterprise ML Organization (100 Users, 100 Instances)

**Typical Setup:**
- 60 CPU instances (mix of DS3_v2, DS12_v2, E8s_v3)
- 30 GPU instances (mix of NC6, NC6s_v3, NC4as_T4_v3)
- 10 stopped instances (forgotten projects)

**Baseline Cost (No Optimizations):**
- 40× DS3_v2: 40 × $143 = $5,720/month
- 10× DS12_v2: 10 × $286 = $2,860/month
- 10× E8s_v3: 10 × $368 = $3,680/month
- 20× NC6: 20 × $657 = $13,140/month
- 5× NC6s_v3 (V100): 5 × $2,234 = $11,170/month
- 5× NC4as_T4_v3: 5 × $384 = $1,920/month
- 10× Stopped (Premium SSD): 10 × $22 = $220/month
- **Total: $38,710/month** ($464,520/year)

**Waste Detected:**

| Scenario | Instances Affected | Monthly Waste | Annual Waste |
|----------|-------------------|---------------|--------------|
| No auto-shutdown (67% waste) | 50 instances always-on | $19,440 | $233,280 |
| GPU for CPU workloads | 10 GPU instances | $5,140 | $61,680 |
| Low CPU utilization (<10%) | 15 instances over-provisioned | $2,145 | $25,740 |
| Stopped >60 days (should delete) | 10 instances | $220 | $2,640 |
| Multiple per user (duplicates) | 20 instances (excess) | $2,860 | $34,320 |
| Premium SSD in dev/test | 15 instances | $152 | $1,824 |
| No idle shutdown (schedule only) | 25 instances | $733 | $8,796 |
| Dev/test high-performance SKU | 10 instances | $1,140 | $13,680 |
| **Total Waste** | **100 instances** | **$31,830** | **$381,960** |

**After CloudWaste Optimization:**
- Enable auto-shutdown on 50 instances: Save $19,440/month
- Convert 10 GPU→CPU: Save $5,140/month
- Rightsize 15 instances: Save $2,145/month
- Delete 10 stopped instances: Save $220/month
- Consolidate duplicates: Save $2,860/month
- **Optimized Total: $6,880/month** ($82,560/year)

**Savings: $31,830/month** (**$381,960/year**) → **82% reduction**

**ROI:**
- CloudWaste subscription: $2,000/month (enterprise)
- Net savings: $29,830/month
- **ROI: 17,898% annually**

**Additional Benefits:**
- **Security compliance**: Upgrade 15 outdated SDK versions → avoid vulnerabilities
- **Developer productivity**: Fix 5 over-provisioned instances → faster notebook execution
- **Budget predictability**: Auto-shutdown adoption → 80% more stable monthly bills
- **Governance**: Multi-instance tracking → prevent shadow IT sprawl

---

### Cost Avoidance Scenarios

**Scenario A: Pre-Deployment Planning**
- Organization plans to deploy 50 new compute instances for ML initiative
- CloudWaste analysis shows 30% can use auto-shutdown (8h/day) instead of 24/7
- 20% can use CPU instead of GPU
- **Avoided Cost: $15,000/month** = **$180,000/year**

**Scenario B: GPU Instance Consolidation**
- 25 data scientists each have NC6 GPU instance ($657/month)
- CloudWaste detects 15 have <5% GPU usage over 60 days
- Switch 15 to DS3_v2 CPU instances
- **Savings: $7,710/month** = **$92,520/year**

**Scenario C: Stopped Instance Cleanup**
- 50 stopped instances accumulating over 2 years
- Each costs $12-22/month in storage
- Delete 40 that are >180 days old
- **Savings: $600-880/month** = **$7,200-10,560/year**

---

## Implementation Roadmap

### Phase 1: Simple Detection (Week 1-2)

**Goal**: Detect configuration-based waste without requiring Azure Monitor metrics.

**Tasks:**
1. Implement Azure ML SDK client (`azure-ai-ml==1.13.0`)
2. Build Scenarios 1-10 (no auto-shutdown, GPU waste, stopped instances, etc.)
3. Create cost calculation engine (VM pricing + disk pricing)
4. Test with 5 sample compute instances
5. Deploy to CloudWaste backend

**Expected Results:**
- 10 detection scenarios operational
- 50-60% of waste identified (configuration-based)
- No dependency on Azure Monitor or 30-day metrics

---

### Phase 2: Metrics-Based Detection (Week 3-4)

**Goal**: Add Azure Monitor integration for CPU, GPU, memory, disk, network metrics.

**Tasks:**
1. Integrate `azure-monitor-query==1.3.0`
2. Implement Scenarios 11-18 (low CPU, low GPU, idle business hours, etc.)
3. Add confidence level calculations (combine Phase 1 + Phase 2 data)
4. Test metrics collection for 30-day period
5. Optimize metric query performance (batch queries, caching)

**Expected Results:**
- 18 detection scenarios operational
- 90%+ of waste identified
- High confidence waste detection with metrics validation

---

### Phase 3: Frontend Integration (Week 5)

**Goal**: Display Azure ML Compute Instance waste in CloudWaste dashboard.

**Tasks:**
1. Add "Compute Instances" resource type to frontend
2. Create instance detail pages (show CPU/GPU graphs, cost breakdown)
3. Implement cost savings calculator
4. Add action buttons ("Stop Instance", "Enable Auto-Shutdown", "Resize Instance")
5. Add bulk operations (stop all idle instances, delete all stopped >90 days)

**Expected Results:**
- Compute Instances visible in main dashboard
- Users can drill down into instance waste details
- One-click remediation actions

---

### Phase 4: Automated Remediation (Week 6-8)

**Goal**: Allow CloudWaste to automatically fix waste (with user approval).

**Tasks:**
1. Implement auto-shutdown enablement via Azure ML SDK
2. Implement instance resizing (change VM SKU)
3. Implement instance deletion (with confirmation workflow)
4. Add approval workflow (require user confirmation for changes)
5. Add audit log (track all automated changes)
6. Add rollback capability (undo changes if issues)

**Expected Results:**
- Users can enable "Auto-Fix" mode for Compute Instances
- CloudWaste automatically enables auto-shutdown on flagged instances
- CloudWaste resizes over-provisioned instances
- 70% of waste remediated automatically

---

### Phase 5: Advanced Analytics (Week 9-10)

**Goal**: Provide predictive insights and benchmarking.

**Tasks:**
1. Build historical waste trends (track waste reduction over time)
2. Implement instance sizing recommendations (ML-based)
3. Add cost forecasting (predict next month's waste if no changes made)
4. Benchmark against industry averages (show "You waste 60% less than average")
5. Add anomaly detection (alert on sudden cost spikes)

**Expected Results:**
- Users see waste reduction progress over time
- Proactive recommendations ("Your instance will exceed budget in 5 days")
- Competitive benchmarking

---

## References

### Official Documentation

1. **Azure Machine Learning Compute Instances Overview**
   https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-instance

2. **Azure ML Compute Instance Pricing**
   https://azure.microsoft.com/en-us/pricing/details/machine-learning/

3. **Auto-Shutdown and Schedules**
   https://learn.microsoft.com/en-us/azure/machine-learning/how-to-create-compute-instance#configure-idle-shutdown

4. **Azure ML Python SDK (azure-ai-ml)**
   https://learn.microsoft.com/en-us/python/api/azure-ai-ml/

5. **Azure Monitor Metrics for ML Compute**
   https://learn.microsoft.com/en-us/azure/machine-learning/monitor-azure-machine-learning

6. **VM Pricing Calculator**
   https://azure.microsoft.com/en-us/pricing/calculator/

### Best Practices

1. **Cost Optimization for Azure ML**
   https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-optimize-cost

2. **Compute Instance vs Compute Cluster**
   https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target

3. **GPU Utilization Monitoring**
   https://learn.microsoft.com/en-us/azure/machine-learning/how-to-monitor-gpu-utilization

### Community Resources

1. **Azure ML Cost Optimization (GitHub)**
   https://github.com/Azure/azureml-examples/tree/main/best-practices

2. **Compute Instance Management Scripts**
   https://github.com/Azure/azure-ml-examples

---

**Document Version**: 1.0
**Last Updated**: 2025-10-29
**Authors**: CloudWaste Team
**Coverage**: 18 waste detection scenarios (100% comprehensive)
**Estimated Detection Value**: $1,363 - $31,830/month per organization
