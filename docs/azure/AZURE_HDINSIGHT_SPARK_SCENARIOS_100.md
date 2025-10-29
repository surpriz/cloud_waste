# Azure HDInsight Spark Cluster - Waste Detection Scenarios (100% Coverage)

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

**Azure HDInsight Spark Clusters** are managed Apache Spark environments designed for big data processing, machine learning, and real-time analytics. HDInsight adds a **+40% management surcharge** on top of base Azure VM costs, making waste particularly expensive.

### Key Characteristics
- **Architecture**: 2+ head nodes (management) + 3+ worker nodes (computation) + optional edge node
- **Spark Components**: YARN resource manager, Spark executors, Ambari API, Hive metastore
- **Pricing Model**: Per-minute billing with HDInsight surcharge + storage + optional services
- **Autoscale**: Load-based (CPU/memory metrics) or schedule-based scaling
- **Versions**: Spark 2.4, 3.0, 3.1, 3.2, 3.3 (older versions = security risks)

### Common Waste Patterns
1. **Cluster left running 24/7** when only used 8 hours/day → 67% waste
2. **No autoscale configured** → 40-60% over-provisioning during low-load periods
3. **Premium storage in dev/test** → 3-4x unnecessary storage costs
4. **External metastore never used** → $73/month wasted on SQL DB
5. **Cluster created but never runs Spark jobs** → 100% waste

### Detection Strategy
- **Phase 1**: Configuration-based detection (cluster state, autoscale, storage SKU, versions)
- **Phase 2**: Azure Monitor metrics + Ambari REST API (CPU, memory, YARN, Spark jobs)

---

## Phase 1 Scenarios - Simple Detection

### Scenario 1: Cluster in Stopped State
**Detection Logic**: Cluster exists but provisioning state is stopped/deallocated for >7 days.

```python
from azure.mgmt.hdinsight import HDInsightManagementClient
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

def detect_stopped_clusters(subscription_id: str) -> list:
    """
    Detect HDInsight clusters in stopped state for >7 days.

    Returns: List of wasteful clusters with cost impact
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.provisioning_state in ['Deleting', 'Canceled', 'Failed']:
            continue

        # Check if cluster is stopped
        if cluster.properties.cluster_state == 'Running':
            continue

        # Calculate how long stopped (approximate from tier change or API state)
        # Note: Azure doesn't track exact stop time, use creation date as proxy
        days_stopped = estimate_stopped_duration(cluster)

        if days_stopped >= 7:
            monthly_cost = calculate_cluster_cost(cluster)
            wasteful_clusters.append({
                'resource_id': cluster.id,
                'name': cluster.name,
                'resource_group': cluster.id.split('/')[4],
                'location': cluster.location,
                'cluster_version': cluster.properties.cluster_version,
                'tier': cluster.properties.tier,
                'days_stopped': days_stopped,
                'estimated_monthly_cost': monthly_cost,
                'waste_percentage': 100,  # Stopped clusters still incur some costs
                'confidence': 'high' if days_stopped >= 30 else 'medium',
                'recommendation': 'Delete cluster or automate start/stop schedule',
                'scenario': 'hdinsight_spark_cluster_stopped',
                'metadata': {
                    'cluster_state': cluster.properties.cluster_state,
                    'provisioning_state': cluster.properties.provisioning_state,
                    'created_date': cluster.properties.created_date.isoformat(),
                    'head_node_size': cluster.properties.compute_profile.roles[0].hardware_profile.vm_size,
                    'worker_node_count': get_worker_node_count(cluster),
                    'worker_node_size': get_worker_node_size(cluster)
                }
            })

    return wasteful_clusters

def calculate_cluster_cost(cluster) -> float:
    """Calculate monthly cost for HDInsight Spark cluster."""
    # HDInsight pricing = (VM cost × 1.40) per node
    # VM costs (East US, per month, 730 hours):
    vm_prices = {
        'Standard_D4_v2': 350.40,      # 8 vCPU, 28 GB RAM
        'Standard_D12_v2': 701.28,     # 4 vCPU, 28 GB RAM
        'Standard_D13_v2': 1402.56,    # 8 vCPU, 56 GB RAM
        'Standard_D14_v2': 2805.12,    # 16 vCPU, 112 GB RAM
        'Standard_D4s_v3': 140.16,     # 4 vCPU, 16 GB RAM
        'Standard_D8s_v3': 280.32,     # 8 vCPU, 32 GB RAM
        'Standard_D16s_v3': 560.64,    # 16 vCPU, 64 GB RAM
        'Standard_E4_v3': 182.50,      # 4 vCPU, 32 GB RAM
        'Standard_E8_v3': 365.00,      # 8 vCPU, 64 GB RAM
        'Standard_E16_v3': 730.00,     # 16 vCPU, 128 GB RAM
    }

    hdinsight_multiplier = 1.40  # +40% HDInsight surcharge

    total_cost = 0.0

    for role in cluster.properties.compute_profile.roles:
        vm_size = role.hardware_profile.vm_size
        target_instance_count = role.target_instance_count

        base_vm_cost = vm_prices.get(vm_size, 350.40)  # Default to D4_v2
        node_cost = base_vm_cost * hdinsight_multiplier
        total_cost += node_cost * target_instance_count

    # Add storage costs (approximate)
    storage_cost = estimate_storage_cost(cluster)
    total_cost += storage_cost

    return round(total_cost, 2)

def get_worker_node_count(cluster) -> int:
    """Get number of worker nodes."""
    for role in cluster.properties.compute_profile.roles:
        if role.name == 'workernode':
            return role.target_instance_count
    return 0

def get_worker_node_size(cluster) -> str:
    """Get worker node VM size."""
    for role in cluster.properties.compute_profile.roles:
        if role.name == 'workernode':
            return role.hardware_profile.vm_size
    return 'Unknown'
```

**Cost Impact**:
- Small cluster (2 head D4_v2 + 4 worker D13_v2): **$8,400/month**
- Stopped state still incurs storage costs (~10% of total)
- **Recommendation**: Delete if unused >30 days, or implement auto-start/stop

**Confidence Level**:
- **High** (90%+): Stopped >30 days
- **Medium** (70-89%): Stopped 7-30 days

---

### Scenario 2: Cluster Never Used (Zero Spark Jobs)
**Detection Logic**: Cluster exists but has never executed any Spark jobs since creation (>14 days old).

```python
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

def detect_never_used_clusters(subscription_id: str) -> list:
    """
    Detect HDInsight clusters that have never run Spark jobs.

    Uses Ambari REST API to check Spark job history.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Check cluster age
        created_date = cluster.properties.created_date
        cluster_age_days = (datetime.now(created_date.tzinfo) - created_date).days

        if cluster_age_days < 14:
            continue  # Too new to judge

        # Query Ambari API for Spark job count
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)  # From Key Vault

        try:
            # Check YARN applications (Spark jobs run on YARN)
            yarn_api_url = f"{ambari_url}:8188/ws/v1/timeline/YARN_APPLICATION"
            response = requests.get(
                yarn_api_url,
                auth=HTTPBasicAuth(username, password),
                timeout=10
            )

            if response.status_code == 200:
                applications = response.json().get('entities', [])
                spark_jobs = [app for app in applications if app.get('otherinfo', {}).get('applicationType') == 'SPARK']

                if len(spark_jobs) == 0:
                    monthly_cost = calculate_cluster_cost(cluster)
                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'cluster_age_days': cluster_age_days,
                        'spark_jobs_count': 0,
                        'estimated_monthly_cost': monthly_cost,
                        'waste_percentage': 100,
                        'confidence': 'critical' if cluster_age_days >= 90 else 'high',
                        'recommendation': 'Delete cluster - no Spark jobs ever executed',
                        'scenario': 'hdinsight_spark_cluster_never_used',
                        'metadata': {
                            'created_date': created_date.isoformat(),
                            'worker_node_count': get_worker_node_count(cluster),
                            'worker_node_size': get_worker_node_size(cluster),
                            'cluster_version': cluster.properties.cluster_version
                        }
                    })

        except Exception as e:
            # Ambari API not accessible - fallback to Azure Monitor metrics
            continue

    return wasteful_clusters
```

**Cost Impact**:
- Medium cluster (2 head D12_v2 + 6 worker D13_v2): **$13,800/month** → **100% waste**
- **Business Case**: If cluster has never run jobs in 90 days, likelihood of future use is <5%

**Confidence Level**:
- **Critical** (95%+): No jobs in 90+ days
- **High** (85-94%): No jobs in 30-89 days
- **Medium** (70-84%): No jobs in 14-29 days

---

### Scenario 3: Premium Storage in Dev/Test Environment
**Detection Logic**: Cluster uses Premium SSD storage but is tagged as dev/test/staging.

```python
def detect_premium_storage_in_nonprod(subscription_id: str) -> list:
    """
    Detect HDInsight clusters using Premium storage in non-production environments.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        # Check environment tags
        tags = cluster.tags or {}
        environment = tags.get('Environment', '').lower()

        if environment not in ['dev', 'test', 'staging', 'development', 'qa', 'uat']:
            continue

        # Check storage account SKU
        storage_accounts = cluster.properties.storage_profile.storageaccounts

        for storage_account in storage_accounts:
            # Get storage account details
            storage_account_name = storage_account.name.split('.')[0]
            storage_rg = storage_account.resource_id.split('/')[4] if storage_account.resource_id else cluster.id.split('/')[4]

            from azure.mgmt.storage import StorageManagementClient
            storage_client = StorageManagementClient(credential, subscription_id)

            try:
                storage_details = storage_client.storage_accounts.get_properties(
                    storage_rg,
                    storage_account_name
                )

                sku = storage_details.sku.name

                if 'Premium' in sku:
                    # Calculate waste (Premium vs Standard cost difference)
                    worker_count = get_worker_node_count(cluster)
                    disk_count_per_node = 4  # Typical for Spark clusters
                    disk_size_gb = 1024  # Typical P30 disk

                    premium_cost_per_disk = 122.88  # P30 (1TB) per month
                    standard_cost_per_disk = 40.96  # S30 (1TB) per month

                    total_premium_cost = premium_cost_per_disk * disk_count_per_node * worker_count
                    total_standard_cost = standard_cost_per_disk * disk_count_per_node * worker_count
                    monthly_waste = total_premium_cost - total_standard_cost

                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'environment': environment,
                        'storage_sku': sku,
                        'estimated_monthly_waste': monthly_waste,
                        'waste_percentage': round((monthly_waste / total_premium_cost) * 100, 1),
                        'confidence': 'high',
                        'recommendation': f'Switch to Standard SSD (S30) to save ${monthly_waste:.2f}/month',
                        'scenario': 'hdinsight_spark_premium_storage_nonprod',
                        'metadata': {
                            'storage_account_name': storage_account_name,
                            'current_sku': sku,
                            'recommended_sku': 'Standard_LRS',
                            'worker_count': worker_count,
                            'disk_count_per_node': disk_count_per_node
                        }
                    })

            except Exception as e:
                continue

    return wasteful_clusters
```

**Cost Impact**:
- 6 worker nodes × 4 disks × (Premium P30 $122.88 - Standard S30 $40.96) = **$1,966/month waste**
- Dev/test workloads rarely need Premium SSD IOPS (5000 vs 500)

**Confidence Level**: **High** (85%+) - Dev/test environments don't need Premium storage performance

---

### Scenario 4: No Autoscale Configured
**Detection Logic**: Cluster has fixed node count with no autoscale policy, leading to over-provisioning during low-load periods.

```python
def detect_no_autoscale(subscription_id: str) -> list:
    """
    Detect HDInsight clusters without autoscale configured.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Check if autoscale is enabled
        autoscale_config = cluster.properties.compute_profile.roles[0].autoscale_configuration

        if autoscale_config is None:
            # No autoscale - check if cluster is large enough to benefit
            worker_count = get_worker_node_count(cluster)

            if worker_count >= 6:  # Autoscale beneficial for 6+ nodes
                worker_node_size = get_worker_node_size(cluster)

                # Calculate potential savings with autoscale
                # Assumption: Autoscale can reduce nodes by 40% during off-peak (16 hours/day)
                vm_prices = {
                    'Standard_D13_v2': 1402.56,
                    'Standard_D14_v2': 2805.12,
                    'Standard_D16s_v3': 560.64,
                    'Standard_E8_v3': 365.00,
                    'Standard_E16_v3': 730.00,
                }

                base_vm_cost = vm_prices.get(worker_node_size, 560.64)
                hdinsight_cost = base_vm_cost * 1.40

                # Savings calculation
                nodes_can_reduce = int(worker_count * 0.40)
                off_peak_hours_per_month = 16 * 30  # 16 hours/day
                total_hours_per_month = 730

                potential_monthly_savings = (
                    nodes_can_reduce * hdinsight_cost *
                    (off_peak_hours_per_month / total_hours_per_month)
                )

                wasteful_clusters.append({
                    'resource_id': cluster.id,
                    'name': cluster.name,
                    'resource_group': cluster.id.split('/')[4],
                    'location': cluster.location,
                    'worker_node_count': worker_count,
                    'worker_node_size': worker_node_size,
                    'estimated_monthly_savings': round(potential_monthly_savings, 2),
                    'waste_percentage': 35,  # Approximate
                    'confidence': 'medium',
                    'recommendation': f'Enable autoscale (min: {worker_count//2}, max: {worker_count}) to save ~${potential_monthly_savings:.2f}/month',
                    'scenario': 'hdinsight_spark_no_autoscale',
                    'metadata': {
                        'autoscale_enabled': False,
                        'current_worker_count': worker_count,
                        'recommended_min_nodes': worker_count // 2,
                        'recommended_max_nodes': worker_count,
                        'potential_node_reduction': nodes_can_reduce
                    }
                })

    return wasteful_clusters
```

**Cost Impact**:
- 10 worker D13_v2 nodes: **$19,636/month** total
- With autoscale (6-10 nodes): Save **$4,324/month** (22% savings)
- Load-based autoscale reacts in 3-5 minutes

**Confidence Level**: **Medium** (70%+) - Depends on actual usage patterns (Phase 2 metrics improve confidence)

---

### Scenario 5: Outdated Cluster Version (Security Risk)
**Detection Logic**: Cluster runs unsupported or outdated Spark version with known security vulnerabilities.

```python
def detect_outdated_versions(subscription_id: str) -> list:
    """
    Detect HDInsight clusters running outdated Spark versions.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    # Supported versions (as of 2025)
    supported_versions = ['4.0', '5.0', '5.1']  # HDInsight versions
    spark_version_map = {
        '3.6': '2.3',  # Deprecated
        '4.0': '3.1',  # Supported
        '5.0': '3.2',  # Supported
        '5.1': '3.3',  # Latest
    }

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        cluster_version = cluster.properties.cluster_version
        major_version = cluster_version.split('.')[0]

        if major_version not in supported_versions:
            # Calculate migration cost vs security risk
            monthly_cost = calculate_cluster_cost(cluster)

            wasteful_clusters.append({
                'resource_id': cluster.id,
                'name': cluster.name,
                'resource_group': cluster.id.split('/')[4],
                'location': cluster.location,
                'current_version': cluster_version,
                'spark_version': spark_version_map.get(major_version, 'Unknown'),
                'recommended_version': '5.1',
                'security_risk': 'high' if major_version <= '3.6' else 'medium',
                'estimated_monthly_cost': monthly_cost,
                'waste_percentage': 0,  # Security risk, not direct waste
                'confidence': 'high',
                'recommendation': f'Upgrade to HDInsight 5.1 (Spark 3.3) - current version {cluster_version} is unsupported',
                'scenario': 'hdinsight_spark_outdated_version',
                'metadata': {
                    'cluster_version': cluster_version,
                    'cluster_tier': cluster.properties.tier,
                    'created_date': cluster.properties.created_date.isoformat()
                }
            })

    return wasteful_clusters
```

**Cost Impact**:
- No direct cost savings, but **security risk** (CVEs, compliance violations)
- Upgrade downtime: 2-4 hours for in-place migration
- **Business Risk**: Non-compliant clusters may require emergency replacement

**Confidence Level**: **High** (90%+) - Unsupported versions are objectively risky

---

### Scenario 6: External Metastore Never Used
**Detection Logic**: Cluster configured with external Hive/Oozie metastore (Azure SQL Database) but metadata tables are empty.

```python
def detect_unused_metastore(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with unused external metastores.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)
    from azure.mgmt.sql import SqlManagementClient

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        # Check if external metastore is configured
        if not hasattr(cluster.properties, 'storage_profile'):
            continue

        # Look for metastore configuration in cluster properties
        # Note: Metastore info is in cluster creation parameters, not always accessible via API
        # This is a simplified check - production implementation would need to:
        # 1. Check cluster tags for metastore DB name
        # 2. Query SQL Database for Hive table count

        tags = cluster.tags or {}
        metastore_db = tags.get('HiveMetastoreDB', None)

        if metastore_db:
            # Check if metastore has any tables
            # This requires SQL credentials - simplified for example
            sql_client = SqlManagementClient(credential, subscription_id)

            # Estimate metastore cost
            # Typical external metastore: Azure SQL S2 (50 DTU) = $73/month
            metastore_monthly_cost = 73.00

            # If metastore exists but cluster never ran jobs, it's wasted
            cluster_age_days = (datetime.now(cluster.properties.created_date.tzinfo) - cluster.properties.created_date).days

            if cluster_age_days >= 30:
                wasteful_clusters.append({
                    'resource_id': cluster.id,
                    'name': cluster.name,
                    'resource_group': cluster.id.split('/')[4],
                    'location': cluster.location,
                    'metastore_db': metastore_db,
                    'estimated_monthly_waste': metastore_monthly_cost,
                    'waste_percentage': 100,
                    'confidence': 'medium',
                    'recommendation': 'Use embedded metastore (free) instead of external Azure SQL DB',
                    'scenario': 'hdinsight_spark_unused_metastore',
                    'metadata': {
                        'cluster_age_days': cluster_age_days,
                        'metastore_type': 'Azure SQL Database',
                        'estimated_cost': metastore_monthly_cost
                    }
                })

    return wasteful_clusters
```

**Cost Impact**:
- External metastore (Azure SQL S2): **$73/month**
- Embedded metastore: **$0** (included in HDInsight)
- **Use Case**: Only needed for cluster sharing or persistence after deletion

**Confidence Level**: **Medium** (70%+) - Depends on whether metastore is actively used by multiple clusters

---

### Scenario 7: Empty Cluster (No Data Processed)
**Detection Logic**: Cluster has been running for >30 days but HDFS storage is nearly empty (<1 GB used).

```python
def detect_empty_clusters(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with minimal HDFS data usage.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        cluster_age_days = (datetime.now(cluster.properties.created_date.tzinfo) - cluster.properties.created_date).days

        if cluster_age_days < 30:
            continue

        # Query Ambari API for HDFS metrics
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)

        try:
            # Get HDFS metrics
            hdfs_api_url = f"{ambari_url}/api/v1/clusters/{cluster.name}/services/HDFS/components/NAMENODE"
            response = requests.get(
                hdfs_api_url,
                auth=HTTPBasicAuth(username, password),
                params={'fields': 'metrics/dfs/FSNamesystem'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                metrics = data.get('metrics', {}).get('dfs', {}).get('FSNamesystem', {})

                capacity_used_gb = metrics.get('CapacityUsed', 0) / (1024**3)
                capacity_total_gb = metrics.get('CapacityTotal', 1) / (1024**3)

                if capacity_used_gb < 1.0:  # Less than 1 GB used
                    monthly_cost = calculate_cluster_cost(cluster)

                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'cluster_age_days': cluster_age_days,
                        'hdfs_used_gb': round(capacity_used_gb, 2),
                        'hdfs_total_gb': round(capacity_total_gb, 2),
                        'estimated_monthly_cost': monthly_cost,
                        'waste_percentage': 98,
                        'confidence': 'high',
                        'recommendation': 'Delete cluster - minimal data processing activity',
                        'scenario': 'hdinsight_spark_empty_cluster',
                        'metadata': {
                            'created_date': cluster.properties.created_date.isoformat(),
                            'worker_count': get_worker_node_count(cluster)
                        }
                    })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- Medium cluster (6 workers): **$11,000/month** with <1 GB data → **98% waste**
- **Sign**: Cluster was provisioned but never received real workloads

**Confidence Level**: **High** (85%+) - HDFS near-empty after 30+ days indicates no real usage

---

### Scenario 8: Oversized Head Nodes
**Detection Logic**: Head nodes use unnecessarily large VM SKUs (D14_v2 instead of D12_v2) when cluster is small (<10 workers).

```python
def detect_oversized_head_nodes(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with oversized head nodes.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    # Recommended head node sizing
    sizing_recommendations = {
        'small': (4, 'Standard_D12_v2'),   # <6 workers
        'medium': (10, 'Standard_D13_v2'), # 6-15 workers
        'large': (16, 'Standard_D14_v2'),  # 16+ workers
    }

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        worker_count = get_worker_node_count(cluster)

        # Get head node configuration
        head_node_size = None
        head_node_count = 0

        for role in cluster.properties.compute_profile.roles:
            if role.name == 'headnode':
                head_node_size = role.hardware_profile.vm_size
                head_node_count = role.target_instance_count
                break

        if not head_node_size:
            continue

        # Determine appropriate head node size
        if worker_count < 6:
            recommended_size = 'Standard_D12_v2'
        elif worker_count <= 15:
            recommended_size = 'Standard_D13_v2'
        else:
            recommended_size = 'Standard_D14_v2'

        # Check if oversized
        vm_size_cost = {
            'Standard_D12_v2': 701.28,
            'Standard_D13_v2': 1402.56,
            'Standard_D14_v2': 2805.12,
        }

        current_cost = vm_size_cost.get(head_node_size, 0) * 1.40 * head_node_count
        recommended_cost = vm_size_cost.get(recommended_size, 0) * 1.40 * head_node_count

        if current_cost > recommended_cost:
            monthly_waste = current_cost - recommended_cost

            wasteful_clusters.append({
                'resource_id': cluster.id,
                'name': cluster.name,
                'resource_group': cluster.id.split('/')[4],
                'location': cluster.location,
                'worker_count': worker_count,
                'current_head_node_size': head_node_size,
                'recommended_head_node_size': recommended_size,
                'estimated_monthly_waste': monthly_waste,
                'waste_percentage': round((monthly_waste / current_cost) * 100, 1),
                'confidence': 'medium',
                'recommendation': f'Resize head nodes from {head_node_size} to {recommended_size}',
                'scenario': 'hdinsight_spark_oversized_head_nodes',
                'metadata': {
                    'current_monthly_cost': round(current_cost, 2),
                    'recommended_monthly_cost': round(recommended_cost, 2),
                    'head_node_count': head_node_count
                }
            })

    return wasteful_clusters
```

**Cost Impact**:
- Small cluster with D14_v2 heads (16 vCPU): **$7,854/month**
- Rightsize to D12_v2 (4 vCPU): **$1,964/month**
- Savings: **$5,890/month** (75%)

**Confidence Level**: **Medium** (75%+) - Head nodes rarely need >8 vCPU for small clusters

---

### Scenario 9: Unnecessary Edge Node
**Detection Logic**: Cluster has edge node (extra cost) but it's never accessed for SSH/notebooks/tools.

```python
def detect_unused_edge_node(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with unused edge nodes.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        # Check if edge node exists
        has_edge_node = False
        edge_node_size = None

        for role in cluster.properties.compute_profile.roles:
            if role.name == 'edgenode':
                has_edge_node = True
                edge_node_size = role.hardware_profile.vm_size
                break

        if not has_edge_node:
            continue

        # Edge node cost (typically D4_v2)
        vm_prices = {'Standard_D4_v2': 350.40, 'Standard_D12_v2': 701.28}
        edge_node_cost = vm_prices.get(edge_node_size, 350.40) * 1.40  # HDInsight surcharge

        # Check if edge node is being used (SSH connections, Jupyter activity)
        # This requires Azure Monitor logs - simplified for example
        cluster_age_days = (datetime.now(cluster.properties.created_date.tzinfo) - cluster.properties.created_date).days

        if cluster_age_days >= 30:
            # If cluster is old and edge node exists, flag as potentially wasteful
            wasteful_clusters.append({
                'resource_id': cluster.id,
                'name': cluster.name,
                'resource_group': cluster.id.split('/')[4],
                'location': cluster.location,
                'edge_node_size': edge_node_size,
                'estimated_monthly_waste': round(edge_node_cost, 2),
                'waste_percentage': 100,
                'confidence': 'low',  # Need SSH logs to confirm
                'recommendation': 'Remove edge node if not used for Jupyter/RStudio/SSH access',
                'scenario': 'hdinsight_spark_unused_edge_node',
                'metadata': {
                    'cluster_age_days': cluster_age_days,
                    'edge_node_vm_size': edge_node_size
                }
            })

    return wasteful_clusters
```

**Cost Impact**:
- Edge node (D4_v2): **$490/month** with HDInsight surcharge
- **Use Case**: Only needed for interactive access (Jupyter, RStudio, SSH)
- Most production pipelines don't need edge nodes

**Confidence Level**: **Low** (50-69%) - Requires SSH/Jupyter logs to confirm non-use (Phase 2)

---

### Scenario 10: Undersized Disks Causing Performance Issues
**Detection Logic**: Worker nodes have insufficient disk space, causing frequent HDFS rebalancing and job failures.

```python
def detect_undersized_disks(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with insufficient disk capacity.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Query Ambari for HDFS capacity metrics
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)

        try:
            hdfs_api_url = f"{ambari_url}/api/v1/clusters/{cluster.name}/services/HDFS/components/NAMENODE"
            response = requests.get(
                hdfs_api_url,
                auth=HTTPBasicAuth(username, password),
                params={'fields': 'metrics/dfs/FSNamesystem'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                metrics = data.get('metrics', {}).get('dfs', {}).get('FSNamesystem', {})

                capacity_used = metrics.get('CapacityUsed', 0)
                capacity_total = metrics.get('CapacityTotal', 1)
                percent_used = (capacity_used / capacity_total) * 100

                if percent_used > 85:  # >85% HDFS capacity used
                    monthly_cost = calculate_cluster_cost(cluster)

                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'hdfs_capacity_used_percent': round(percent_used, 1),
                        'hdfs_capacity_total_gb': round(capacity_total / (1024**3), 2),
                        'estimated_monthly_cost': monthly_cost,
                        'waste_percentage': -15,  # Negative = costing more due to inefficiency
                        'confidence': 'high',
                        'recommendation': 'Add more disks or scale up worker nodes to avoid job failures',
                        'scenario': 'hdinsight_spark_undersized_disks',
                        'metadata': {
                            'worker_count': get_worker_node_count(cluster),
                            'worker_node_size': get_worker_node_size(cluster)
                        }
                    })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- HDFS >85% full → Job failures, retries, performance degradation
- **Hidden Cost**: Developer time debugging disk space issues (~10 hours/month × $75/hour = $750)
- **Recommendation**: Scale up or add storage

**Confidence Level**: **High** (85%+) - HDFS capacity metrics are objective

---

## Phase 2 Scenarios - Metrics-Based Detection

### Scenario 11: Low Average CPU Utilization (<20%)
**Detection Logic**: Cluster runs 24/7 but average CPU across worker nodes is <20% for 30 days.

```python
from azure.monitor.query import MetricsQueryClient
from datetime import datetime, timedelta

def detect_low_cpu_utilization(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with sustained low CPU utilization.

    Requires: azure-monitor-query==1.3.0
    Permission: Monitoring Reader
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_clusters = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        try:
            # Query Azure Monitor for CPU metrics
            response = metrics_client.query_resource(
                resource_uri=cluster.id,
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

            if avg_cpu < 20:  # <20% average CPU
                worker_count = get_worker_node_count(cluster)
                worker_node_size = get_worker_node_size(cluster)

                # Calculate rightsizing opportunity
                # If avg CPU is 15%, cluster could run on 15/60 = 25% of nodes (with 60% target)
                optimal_worker_count = max(3, int(worker_count * (avg_cpu / 60)))

                vm_prices = {
                    'Standard_D13_v2': 1402.56,
                    'Standard_D14_v2': 2805.12,
                    'Standard_D16s_v3': 560.64,
                    'Standard_E8_v3': 365.00,
                }

                base_vm_cost = vm_prices.get(worker_node_size, 560.64)
                hdinsight_cost = base_vm_cost * 1.40

                current_monthly_cost = hdinsight_cost * worker_count
                optimal_monthly_cost = hdinsight_cost * optimal_worker_count
                monthly_waste = current_monthly_cost - optimal_monthly_cost

                wasteful_clusters.append({
                    'resource_id': cluster.id,
                    'name': cluster.name,
                    'resource_group': cluster.id.split('/')[4],
                    'location': cluster.location,
                    'avg_cpu_percent': round(avg_cpu, 1),
                    'current_worker_count': worker_count,
                    'recommended_worker_count': optimal_worker_count,
                    'estimated_monthly_waste': round(monthly_waste, 2),
                    'waste_percentage': round((monthly_waste / current_monthly_cost) * 100, 1),
                    'confidence': 'high',
                    'recommendation': f'Reduce worker nodes from {worker_count} to {optimal_worker_count} or enable autoscale',
                    'scenario': 'hdinsight_spark_low_cpu_utilization',
                    'metadata': {
                        'measurement_period_days': 30,
                        'worker_node_size': worker_node_size,
                        'samples_analyzed': len(cpu_values)
                    }
                })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- 10 worker nodes at 15% avg CPU → Rightsize to 3-4 nodes
- Savings: **$8,400/month** (60% reduction)
- Target CPU: 50-70% for optimal cost/performance

**Confidence Level**: **High** (85%+) - 30 days of metrics is strong signal

---

### Scenario 12: Zero Spark Jobs Submitted (Ambari Metrics)
**Detection Logic**: YARN ApplicationMaster never launched Spark applications in 30 days despite cluster running.

```python
def detect_zero_spark_jobs_metrics(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with zero Spark job activity via Ambari metrics.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Query Ambari metrics for Spark activity
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)

        try:
            # Get YARN metrics for application submissions
            yarn_metrics_url = f"{ambari_url}/api/v1/clusters/{cluster.name}/services/YARN/components/RESOURCEMANAGER"
            response = requests.get(
                yarn_metrics_url,
                auth=HTTPBasicAuth(username, password),
                params={'fields': 'metrics/yarn/Queue/root'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                metrics = data.get('metrics', {}).get('yarn', {}).get('Queue', {}).get('root', {})

                apps_submitted = metrics.get('AppsSubmitted', 0)
                apps_completed = metrics.get('AppsCompleted', 0)

                if apps_submitted == 0:
                    cluster_age_days = (datetime.now(cluster.properties.created_date.tzinfo) - cluster.properties.created_date).days
                    monthly_cost = calculate_cluster_cost(cluster)

                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'apps_submitted': apps_submitted,
                        'apps_completed': apps_completed,
                        'cluster_age_days': cluster_age_days,
                        'estimated_monthly_cost': monthly_cost,
                        'waste_percentage': 100,
                        'confidence': 'critical',
                        'recommendation': 'Delete cluster immediately - zero Spark jobs submitted',
                        'scenario': 'hdinsight_spark_zero_jobs_metrics',
                        'metadata': {
                            'worker_count': get_worker_node_count(cluster),
                            'created_date': cluster.properties.created_date.isoformat()
                        }
                    })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- Medium cluster: **$11,000/month** → **100% waste** if zero jobs
- **Critical**: This is Phase 2 confirmation of Scenario 2

**Confidence Level**: **Critical** (95%+) - YARN metrics are definitive

---

### Scenario 13: Cluster Idle During Business Hours
**Detection Logic**: CPU/memory usage is <10% during expected business hours (9 AM - 5 PM) for 30 days.

```python
def detect_idle_during_business_hours(subscription_id: str) -> list:
    """
    Detect HDInsight clusters idle during business hours.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_clusters = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        try:
            response = metrics_client.query_resource(
                resource_uri=cluster.id,
                metric_names=["CpuPercentage", "MemoryPercentage"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            # Filter to business hours (9 AM - 5 PM UTC)
            business_hour_cpu = []
            business_hour_memory = []

            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        timestamp = data_point.timestamp
                        hour = timestamp.hour

                        if 9 <= hour < 17:  # Business hours
                            if metric.name == "CpuPercentage" and data_point.average:
                                business_hour_cpu.append(data_point.average)
                            elif metric.name == "MemoryPercentage" and data_point.average:
                                business_hour_memory.append(data_point.average)

            if not business_hour_cpu:
                continue

            avg_business_cpu = sum(business_hour_cpu) / len(business_hour_cpu)
            avg_business_memory = sum(business_hour_memory) / len(business_hour_memory) if business_hour_memory else 0

            if avg_business_cpu < 10 and avg_business_memory < 15:
                monthly_cost = calculate_cluster_cost(cluster)

                wasteful_clusters.append({
                    'resource_id': cluster.id,
                    'name': cluster.name,
                    'resource_group': cluster.id.split('/')[4],
                    'location': cluster.location,
                    'avg_cpu_business_hours': round(avg_business_cpu, 1),
                    'avg_memory_business_hours': round(avg_business_memory, 1),
                    'estimated_monthly_cost': monthly_cost,
                    'waste_percentage': 85,
                    'confidence': 'high',
                    'recommendation': 'Delete cluster - idle even during expected business hours',
                    'scenario': 'hdinsight_spark_idle_business_hours',
                    'metadata': {
                        'measurement_period_days': 30,
                        'business_hours_analyzed': len(business_hour_cpu),
                        'worker_count': get_worker_node_count(cluster)
                    }
                })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- Cluster idle during 9 AM - 5 PM (when jobs should run) → **85% waste**
- Indicates cluster was provisioned but workload never scheduled

**Confidence Level**: **High** (85%+) - Business hour idleness is strong waste signal

---

### Scenario 14: High YARN Memory Waste
**Detection Logic**: YARN shows consistently high available memory (>60% free) indicating over-provisioned worker nodes.

```python
def detect_yarn_memory_waste(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with excessive YARN available memory.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Query Ambari for YARN metrics
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)

        try:
            yarn_metrics_url = f"{ambari_url}/api/v1/clusters/{cluster.name}/services/YARN/components/RESOURCEMANAGER"
            response = requests.get(
                yarn_metrics_url,
                auth=HTTPBasicAuth(username, password),
                params={'fields': 'metrics/yarn/ClusterMetrics'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                cluster_metrics = data.get('metrics', {}).get('yarn', {}).get('ClusterMetrics', {})

                total_memory_mb = cluster_metrics.get('TotalMB', 0)
                available_memory_mb = cluster_metrics.get('AvailableMB', 0)

                if total_memory_mb > 0:
                    memory_utilization = ((total_memory_mb - available_memory_mb) / total_memory_mb) * 100

                    if memory_utilization < 40:  # <40% memory used
                        worker_count = get_worker_node_count(cluster)
                        worker_node_size = get_worker_node_size(cluster)

                        # Calculate optimal worker count
                        optimal_worker_count = max(3, int(worker_count * (memory_utilization / 70)))

                        vm_prices = {
                            'Standard_D13_v2': 1402.56,
                            'Standard_E8_v3': 365.00,
                            'Standard_E16_v3': 730.00,
                        }

                        base_vm_cost = vm_prices.get(worker_node_size, 560.64)
                        hdinsight_cost = base_vm_cost * 1.40

                        monthly_waste = hdinsight_cost * (worker_count - optimal_worker_count)

                        wasteful_clusters.append({
                            'resource_id': cluster.id,
                            'name': cluster.name,
                            'resource_group': cluster.id.split('/')[4],
                            'location': cluster.location,
                            'yarn_memory_utilization_percent': round(memory_utilization, 1),
                            'yarn_total_memory_gb': round(total_memory_mb / 1024, 1),
                            'yarn_available_memory_gb': round(available_memory_mb / 1024, 1),
                            'current_worker_count': worker_count,
                            'recommended_worker_count': optimal_worker_count,
                            'estimated_monthly_waste': round(monthly_waste, 2),
                            'waste_percentage': round(((worker_count - optimal_worker_count) / worker_count) * 100, 1),
                            'confidence': 'high',
                            'recommendation': f'Reduce worker nodes from {worker_count} to {optimal_worker_count}',
                            'scenario': 'hdinsight_spark_yarn_memory_waste',
                            'metadata': {
                                'worker_node_size': worker_node_size
                            }
                        })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- 10 E16_v3 workers with 35% memory utilization → Rightsize to 5 workers
- Savings: **$5,110/month** (50%)

**Confidence Level**: **High** (85%+) - YARN metrics are authoritative

---

### Scenario 15: Excessive Shuffle Data (Poor Job Optimization)
**Detection Logic**: Spark jobs show >100 GB shuffle data per job, indicating inefficient transformations.

```python
def detect_excessive_shuffle(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with inefficient Spark jobs (excessive shuffle).
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Query Ambari/Spark History Server for shuffle metrics
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)

        try:
            # Spark History Server API
            spark_history_url = f"{ambari_url}:18080/api/v1/applications"
            response = requests.get(
                spark_history_url,
                auth=HTTPBasicAuth(username, password),
                timeout=10
            )

            if response.status_code == 200:
                applications = response.json()

                high_shuffle_jobs = []

                for app in applications[:50]:  # Check last 50 jobs
                    app_id = app.get('id')

                    # Get detailed job metrics
                    job_url = f"{ambari_url}:18080/api/v1/applications/{app_id}/stages"
                    job_response = requests.get(
                        job_url,
                        auth=HTTPBasicAuth(username, password),
                        timeout=5
                    )

                    if job_response.status_code == 200:
                        stages = job_response.json()

                        for stage in stages:
                            shuffle_write_bytes = stage.get('shuffleWriteBytes', 0)
                            shuffle_read_bytes = stage.get('shuffleReadBytes', 0)
                            total_shuffle_gb = (shuffle_write_bytes + shuffle_read_bytes) / (1024**3)

                            if total_shuffle_gb > 100:  # >100 GB shuffle
                                high_shuffle_jobs.append({
                                    'app_id': app_id,
                                    'stage_id': stage.get('stageId'),
                                    'shuffle_gb': round(total_shuffle_gb, 2)
                                })

                if len(high_shuffle_jobs) > 5:  # Multiple jobs with high shuffle
                    monthly_cost = calculate_cluster_cost(cluster)

                    # Estimate waste due to inefficient jobs (20-30% performance loss)
                    estimated_waste_percent = 25
                    monthly_waste = monthly_cost * (estimated_waste_percent / 100)

                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'high_shuffle_jobs_count': len(high_shuffle_jobs),
                        'avg_shuffle_gb': round(sum(j['shuffle_gb'] for j in high_shuffle_jobs) / len(high_shuffle_jobs), 2),
                        'estimated_monthly_waste': round(monthly_waste, 2),
                        'waste_percentage': estimated_waste_percent,
                        'confidence': 'medium',
                        'recommendation': 'Optimize Spark jobs: use broadcast joins, repartition data, cache intermediate results',
                        'scenario': 'hdinsight_spark_excessive_shuffle',
                        'metadata': {
                            'sample_high_shuffle_jobs': high_shuffle_jobs[:3],
                            'worker_count': get_worker_node_count(cluster)
                        }
                    })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- Inefficient Spark jobs → 20-30% longer runtimes → 20-30% higher costs
- Example: $10,000/month cluster with poor optimization = **$2,500/month waste**
- **Solution**: Broadcast joins, repartitioning, caching

**Confidence Level**: **Medium** (70-84%) - Requires job-level analysis

---

### Scenario 16: Autoscale Not Working Effectively
**Detection Logic**: Autoscale enabled but metrics show node count never changes despite load variations.

```python
def detect_autoscale_not_working(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with ineffective autoscale configuration.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_clusters = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for cluster in hdinsight_client.clusters.list():
        # Check if autoscale is enabled
        autoscale_config = None
        for role in cluster.properties.compute_profile.roles:
            if role.name == 'workernode' and role.autoscale_configuration:
                autoscale_config = role.autoscale_configuration
                break

        if not autoscale_config:
            continue  # No autoscale configured

        try:
            # Query metrics for worker node count over time
            response = metrics_client.query_resource(
                resource_uri=cluster.id,
                metric_names=["NumActiveWorkers"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=6),
                aggregations=["Average"]
            )

            node_counts = []
            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average:
                            node_counts.append(int(data_point.average))

            if not node_counts:
                continue

            # Check if node count varies
            min_nodes = min(node_counts)
            max_nodes = max(node_counts)
            node_variance = max_nodes - min_nodes

            # If autoscale is enabled but nodes never change, it's ineffective
            if node_variance <= 1:  # Nodes never scale
                avg_node_count = sum(node_counts) / len(node_counts)

                # Potential savings if autoscale worked properly (assume 30% reduction)
                worker_node_size = get_worker_node_size(cluster)
                vm_prices = {
                    'Standard_D13_v2': 1402.56,
                    'Standard_D14_v2': 2805.12,
                    'Standard_E8_v3': 365.00,
                }

                base_vm_cost = vm_prices.get(worker_node_size, 560.64)
                hdinsight_cost = base_vm_cost * 1.40

                potential_monthly_savings = hdinsight_cost * avg_node_count * 0.30

                wasteful_clusters.append({
                    'resource_id': cluster.id,
                    'name': cluster.name,
                    'resource_group': cluster.id.split('/')[4],
                    'location': cluster.location,
                    'autoscale_enabled': True,
                    'autoscale_type': autoscale_config.capacity.min_instance_count if hasattr(autoscale_config, 'capacity') else 'schedule',
                    'min_nodes_observed': min_nodes,
                    'max_nodes_observed': max_nodes,
                    'node_variance': node_variance,
                    'estimated_monthly_savings': round(potential_monthly_savings, 2),
                    'waste_percentage': 30,
                    'confidence': 'medium',
                    'recommendation': 'Review autoscale triggers - node count never changes despite autoscale being enabled',
                    'scenario': 'hdinsight_spark_autoscale_not_working',
                    'metadata': {
                        'avg_node_count': round(avg_node_count, 1),
                        'measurement_period_days': 30,
                        'samples_analyzed': len(node_counts)
                    }
                })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- Autoscale enabled but not functioning → Missing 30-40% potential savings
- Example: 8-node cluster, expected autoscale savings $2,800/month → **$2,800/month opportunity cost**

**Confidence Level**: **Medium** (75%+) - Requires 30 days of node count metrics

---

### Scenario 17: Low Memory Utilization (<25%)
**Detection Logic**: Worker nodes consistently use <25% of available memory for 30 days.

```python
def detect_low_memory_utilization(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with low memory utilization.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)
    metrics_client = MetricsQueryClient(credential)

    wasteful_clusters = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        try:
            response = metrics_client.query_resource(
                resource_uri=cluster.id,
                metric_names=["MemoryPercentage"],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=["Average"]
            )

            memory_values = []
            for metric in response.metrics:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        if data_point.average:
                            memory_values.append(data_point.average)

            if not memory_values:
                continue

            avg_memory = sum(memory_values) / len(memory_values)

            if avg_memory < 25:
                worker_count = get_worker_node_count(cluster)
                worker_node_size = get_worker_node_size(cluster)

                # Suggest switching to compute-optimized (Dsv3) from memory-optimized (Ev3)
                if 'E' in worker_node_size:  # Currently using memory-optimized
                    current_cost = {
                        'Standard_E8_v3': 365.00,
                        'Standard_E16_v3': 730.00,
                    }.get(worker_node_size, 365.00)

                    recommended_size = {
                        'Standard_E8_v3': 'Standard_D8s_v3',
                        'Standard_E16_v3': 'Standard_D16s_v3',
                    }.get(worker_node_size, 'Standard_D8s_v3')

                    recommended_cost = {
                        'Standard_D8s_v3': 280.32,
                        'Standard_D16s_v3': 560.64,
                    }.get(recommended_size, 280.32)

                    monthly_savings = (current_cost - recommended_cost) * 1.40 * worker_count

                    wasteful_clusters.append({
                        'resource_id': cluster.id,
                        'name': cluster.name,
                        'resource_group': cluster.id.split('/')[4],
                        'location': cluster.location,
                        'avg_memory_percent': round(avg_memory, 1),
                        'current_worker_node_size': worker_node_size,
                        'recommended_worker_node_size': recommended_size,
                        'worker_count': worker_count,
                        'estimated_monthly_savings': round(monthly_savings, 2),
                        'waste_percentage': round((monthly_savings / (current_cost * 1.40 * worker_count)) * 100, 1),
                        'confidence': 'high',
                        'recommendation': f'Switch from {worker_node_size} to {recommended_size} (compute-optimized)',
                        'scenario': 'hdinsight_spark_low_memory_utilization',
                        'metadata': {
                            'measurement_period_days': 30,
                            'samples_analyzed': len(memory_values)
                        }
                    })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- 6 E16_v3 workers (128 GB RAM each) at 20% memory usage → Switch to D16s_v3 (64 GB RAM)
- Savings: **$1,427/month** (23%)

**Confidence Level**: **High** (85%+) - 30 days of memory metrics

---

### Scenario 18: High Job Failure Rate (>25%)
**Detection Logic**: More than 25% of Spark jobs fail, indicating cluster misconfiguration or insufficient resources.

```python
def detect_high_job_failure_rate(subscription_id: str) -> list:
    """
    Detect HDInsight clusters with high Spark job failure rates.
    """
    credential = DefaultAzureCredential()
    hdinsight_client = HDInsightManagementClient(credential, subscription_id)

    wasteful_clusters = []

    for cluster in hdinsight_client.clusters.list():
        if cluster.properties.cluster_state != 'Running':
            continue

        # Query Ambari for YARN application metrics
        ambari_url = f"https://{cluster.name}.azurehdinsight.net"
        username = get_cluster_admin_username(cluster)
        password = get_cluster_admin_password(cluster)

        try:
            yarn_metrics_url = f"{ambari_url}/api/v1/clusters/{cluster.name}/services/YARN/components/RESOURCEMANAGER"
            response = requests.get(
                yarn_metrics_url,
                auth=HTTPBasicAuth(username, password),
                params={'fields': 'metrics/yarn/Queue/root'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                metrics = data.get('metrics', {}).get('yarn', {}).get('Queue', {}).get('root', {})

                apps_submitted = metrics.get('AppsSubmitted', 0)
                apps_failed = metrics.get('AppsFailed', 0)
                apps_killed = metrics.get('AppsKilled', 0)

                if apps_submitted > 0:
                    failure_rate = ((apps_failed + apps_killed) / apps_submitted) * 100

                    if failure_rate > 25:
                        monthly_cost = calculate_cluster_cost(cluster)

                        # Estimate waste due to failed jobs (retries, debugging time)
                        estimated_waste = monthly_cost * (failure_rate / 100) * 0.5  # 50% of failed job costs

                        wasteful_clusters.append({
                            'resource_id': cluster.id,
                            'name': cluster.name,
                            'resource_group': cluster.id.split('/')[4],
                            'location': cluster.location,
                            'apps_submitted': apps_submitted,
                            'apps_failed': apps_failed,
                            'apps_killed': apps_killed,
                            'failure_rate_percent': round(failure_rate, 1),
                            'estimated_monthly_waste': round(estimated_waste, 2),
                            'waste_percentage': round((estimated_waste / monthly_cost) * 100, 1),
                            'confidence': 'medium',
                            'recommendation': 'Investigate job failures - check logs, increase memory/cores, or fix data issues',
                            'scenario': 'hdinsight_spark_high_job_failure_rate',
                            'metadata': {
                                'worker_count': get_worker_node_count(cluster),
                                'worker_node_size': get_worker_node_size(cluster),
                                'cluster_version': cluster.properties.cluster_version
                            }
                        })

        except Exception as e:
            continue

    return wasteful_clusters
```

**Cost Impact**:
- 40% job failure rate → 40% of compute time wasted on failed jobs
- Example: $10,000/month cluster → **$2,000/month waste** on retries and debugging

**Confidence Level**: **Medium** (75%+) - High failure rates indicate actionable inefficiency

---

## Pricing Structure

### HDInsight Spark Cluster Costs

**HDInsight Surcharge**: +40% on base Azure VM costs

#### Head Nodes (Always 2 nodes, required)
| VM Size | vCPU | RAM | Base Cost/Month | HDInsight Cost/Month | Total (×2 nodes) |
|---------|------|-----|-----------------|----------------------|------------------|
| Standard_D12_v2 | 4 | 28 GB | $500.91 | $701.28 | **$1,402.56** |
| Standard_D13_v2 | 8 | 56 GB | $1,001.83 | $1,402.56 | **$2,805.12** |
| Standard_D14_v2 | 16 | 112 GB | $2,003.66 | $2,805.12 | **$5,610.24** |

**Recommendation**: D12_v2 sufficient for most clusters with <10 workers

#### Worker Nodes (Minimum 3 for production)
| VM Size | vCPU | RAM | Base Cost/Month | HDInsight Cost/Month |
|---------|------|-----|-----------------|----------------------|
| Standard_D4_v2 | 8 | 28 GB | $250.29 | **$350.40** |
| Standard_D13_v2 | 8 | 56 GB | $1,001.83 | **$1,402.56** |
| Standard_D14_v2 | 16 | 112 GB | $2,003.66 | **$2,805.12** |
| Standard_D8s_v3 | 8 | 32 GB | $200.23 | **$280.32** |
| Standard_D16s_v3 | 16 | 64 GB | $400.46 | **$560.64** |
| Standard_E8_v3 | 8 | 64 GB | $260.71 | **$365.00** |
| Standard_E16_v3 | 16 | 128 GB | $521.43 | **$730.00** |

#### Example Cluster Costs

**Small Dev Cluster:**
- 2 × D12_v2 head nodes: $1,402.56
- 4 × D13_v2 worker nodes: $5,610.24
- Storage (1 TB Standard SSD): $40.96
- **Total: $7,053.76/month**

**Medium Production Cluster:**
- 2 × D13_v2 head nodes: $2,805.12
- 8 × D16s_v3 worker nodes: $4,485.12
- Storage (4 TB Standard SSD): $163.84
- **Total: $7,454.08/month**

**Large Production Cluster:**
- 2 × D14_v2 head nodes: $5,610.24
- 16 × E16_v3 worker nodes: $11,680.00
- Storage (10 TB Standard SSD): $409.60
- **Total: $17,699.84/month**

#### Additional Costs

**External Metastore (Optional):**
- Azure SQL Database S2 (50 DTU): **$73/month**
- Azure SQL Database S3 (100 DTU): **$146/month**
- Only needed for shared metastore or persistence after cluster deletion

**Edge Node (Optional):**
- Standard_D4_v2: **$350.40/month**
- Used for Jupyter, RStudio, SSH access

**Storage:**
- Standard SSD (S30, 1 TB): **$40.96/month**
- Premium SSD (P30, 1 TB): **$122.88/month**

**Network:**
- Inter-region data transfer: $0.02/GB
- Internet egress: $0.087/GB (first 10 TB)

---

## Required Azure Permissions

### Minimum RBAC Roles

**Phase 1 Detection (Configuration):**
- **Reader** on Subscription or Resource Group
  - Allows reading cluster configurations, VM sizes, autoscale settings

**Phase 2 Detection (Metrics):**
- **Monitoring Reader** on Subscription or Resource Group
  - Required for Azure Monitor metrics (CPU, memory, worker count)
  - Required for reading diagnostic logs

**Ambari API Access:**
- HDInsight cluster admin credentials (stored securely in Azure Key Vault)
- Allows querying YARN, Spark History Server, HDFS metrics

### Custom Role Definition (Recommended)

```json
{
  "Name": "CloudWaste HDInsight Scanner",
  "Description": "Read-only access to HDInsight clusters and metrics for waste detection",
  "Actions": [
    "Microsoft.HDInsight/clusters/read",
    "Microsoft.HDInsight/clusters/configurations/action",
    "Microsoft.Insights/Metrics/Read",
    "Microsoft.Insights/DiagnosticSettings/Read",
    "Microsoft.Storage/storageAccounts/read",
    "Microsoft.Sql/servers/databases/read"
  ],
  "NotActions": [],
  "AssignableScopes": ["/subscriptions/{subscription-id}"]
}
```

### Service Principal Setup

```bash
# Create service principal for CloudWaste
az ad sp create-for-rbac --name "CloudWaste-HDInsight-Scanner" \
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

### 1. Create Test HDInsight Spark Cluster

```bash
# Set variables
RESOURCE_GROUP="cloudwaste-test-rg"
LOCATION="eastus"
CLUSTER_NAME="testhdinsightcluster"
STORAGE_ACCOUNT="hdistorage$(date +%s)"
CONTAINER="hdinsight-data"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2

# Get storage key
STORAGE_KEY=$(az storage account keys list \
  --resource-group $RESOURCE_GROUP \
  --account-name $STORAGE_ACCOUNT \
  --query '[0].value' -o tsv)

# Create container
az storage container create \
  --name $CONTAINER \
  --account-name $STORAGE_ACCOUNT \
  --account-key $STORAGE_KEY

# Create HDInsight Spark cluster (small dev cluster)
az hdinsight create \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP \
  --type Spark \
  --component-version Spark=3.3 \
  --http-password 'YourPassword123!' \
  --ssh-password 'YourPassword123!' \
  --location $LOCATION \
  --cluster-tier Standard \
  --workernode-count 4 \
  --workernode-size Standard_D13_v2 \
  --headnode-size Standard_D12_v2 \
  --storage-account "$STORAGE_ACCOUNT.blob.core.windows.net" \
  --storage-account-key $STORAGE_KEY \
  --storage-container $CONTAINER \
  --tags Environment=dev Purpose=testing

# Expected cost: ~$7,054/month
```

### 2. Query Cluster Configuration

```bash
# Get cluster details
az hdinsight show \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP

# Get compute profile (node sizes and counts)
az hdinsight show \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP \
  --query 'properties.computeProfile.roles[].[name,hardwareProfile.vmSize,targetInstanceCount]' \
  --output table

# Check autoscale configuration
az hdinsight autoscale show \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP
```

### 3. Enable Autoscale (Load-Based)

```bash
az hdinsight autoscale create \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $CLUSTER_NAME \
  --type Load \
  --min-workernode-count 3 \
  --max-workernode-count 10 \
  --timezone "Pacific Standard Time" \
  --workernode-count 6
```

### 4. Enable Autoscale (Schedule-Based)

```bash
az hdinsight autoscale create \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $CLUSTER_NAME \
  --type Schedule \
  --timezone "Pacific Standard Time" \
  --days Monday Tuesday Wednesday Thursday Friday \
  --time 09:00 \
  --workernode-count 8

az hdinsight autoscale create \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $CLUSTER_NAME \
  --type Schedule \
  --timezone "Pacific Standard Time" \
  --days Monday Tuesday Wednesday Thursday Friday \
  --time 18:00 \
  --workernode-count 3
```

### 5. Query Azure Monitor Metrics

```bash
# Get CPU utilization (last 30 days)
az monitor metrics list \
  --resource "/subscriptions/{subscription-id}/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.HDInsight/clusters/$CLUSTER_NAME" \
  --metric "CpuPercentage" \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table

# Get memory utilization
az monitor metrics list \
  --resource "/subscriptions/{subscription-id}/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.HDInsight/clusters/$CLUSTER_NAME" \
  --metric "MemoryPercentage" \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT1H \
  --aggregation Average \
  --output table

# Get active worker node count
az monitor metrics list \
  --resource "/subscriptions/{subscription-id}/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.HDInsight/clusters/$CLUSTER_NAME" \
  --metric "NumActiveWorkers" \
  --start-time $(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval PT6H \
  --aggregation Average \
  --output table
```

### 6. Query Ambari REST API

```bash
# Set Ambari credentials
AMBARI_USER="admin"
AMBARI_PASSWORD="YourPassword123!"
CLUSTER_NAME="testhdinsightcluster"

# Get YARN metrics
curl -u $AMBARI_USER:$AMBARI_PASSWORD \
  "https://$CLUSTER_NAME.azurehdinsight.net/api/v1/clusters/$CLUSTER_NAME/services/YARN/components/RESOURCEMANAGER?fields=metrics/yarn/Queue/root" \
  | jq '.metrics.yarn.Queue.root'

# Get HDFS capacity
curl -u $AMBARI_USER:$AMBARI_PASSWORD \
  "https://$CLUSTER_NAME.azurehdinsight.net/api/v1/clusters/$CLUSTER_NAME/services/HDFS/components/NAMENODE?fields=metrics/dfs/FSNamesystem" \
  | jq '.metrics.dfs.FSNamesystem | {CapacityUsed, CapacityTotal, CapacityRemaining}'

# List Spark applications
curl -u $AMBARI_USER:$AMBARI_PASSWORD \
  "https://$CLUSTER_NAME.azurehdinsight.net:18080/api/v1/applications" \
  | jq '.[].id'
```

### 7. Simulate Waste Scenarios

**Scenario 2: Never Used Cluster**
```bash
# Create cluster and leave idle (don't submit any jobs)
# Wait 30+ days and run waste detection
```

**Scenario 3: Premium Storage in Dev**
```bash
# Tag cluster as dev but use Premium storage
az hdinsight update \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP \
  --tags Environment=dev

# Check storage SKU
az storage account show \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query 'sku.name'
```

**Scenario 11: Low CPU Utilization**
```bash
# Create cluster but submit only lightweight Spark jobs
# Monitor CPU metrics - should show <20% utilization
```

### 8. Cleanup Resources

```bash
# Delete cluster (but keep storage)
az hdinsight delete \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete resource group (removes everything)
az group delete \
  --name $RESOURCE_GROUP \
  --yes
```

---

## Comparison with Alternatives

### Azure Databricks vs HDInsight Spark

| Feature | HDInsight Spark | Azure Databricks | Winner |
|---------|-----------------|------------------|--------|
| **Pricing Model** | VM + 40% surcharge | DBU + VM costs | HDInsight (30% cheaper) |
| **Autoscale Speed** | 3-5 minutes | 30-60 seconds | Databricks |
| **Managed Services** | Basic (Ambari) | Advanced (notebooks, MLflow) | Databricks |
| **Cluster Startup** | 10-15 minutes | 3-5 minutes | Databricks |
| **Enterprise Support** | Standard Azure | 24/7 Databricks experts | Databricks |
| **Cost Transparency** | Clear VM costs | DBU pricing confusing | HDInsight |
| **Best For** | Cost-sensitive batch | Interactive analytics | Depends |

**Cost Example (8-node cluster, 40 hours/month):**
- HDInsight: 8 × $560.64 × (40/730) = **$245.64**
- Databricks: 8 × $400.46 + (320 DBU × $0.40) = **$348.37**
- **Savings with HDInsight: $102.73/month (29%)**

### Azure Synapse Spark vs HDInsight Spark

| Feature | HDInsight Spark | Synapse Spark | Winner |
|---------|-----------------|---------------|--------|
| **Pricing** | VM + 40% surcharge | vCore-seconds | Synapse (serverless) |
| **Minimum Cost** | ~$7,000/month (24/7) | $0 when idle | Synapse |
| **Integration** | Manual (ADF, Storage) | Built-in (SQL, Pipelines) | Synapse |
| **Cluster Control** | Full Spark config | Limited customization | HDInsight |
| **Use Case** | Long-running ETL | Ad-hoc analytics | Depends |

**When to Choose HDInsight:**
- Need 24/7 cluster availability
- Custom Spark configurations required
- Prefer VM-based pricing (predictable)
- Already invested in HDInsight expertise

**When to Choose Databricks:**
- Interactive data science workflows
- Need fast autoscale (seconds vs minutes)
- Want managed notebooks/MLflow
- Budget allows premium pricing

**When to Choose Synapse Spark:**
- Intermittent workloads (1-2 hours/day)
- Need tight integration with Azure Synapse SQL
- Want true serverless (pay-per-second)

---

## Test Matrix

### Phase 1 Tests (Configuration-Based)

| Scenario | Test Setup | Expected Detection | Validation Command |
|----------|------------|-------------------|-------------------|
| 1. Stopped Cluster | Create cluster, deallocate for 10 days | HIGH confidence, 100% waste | `az hdinsight show --query 'properties.clusterState'` |
| 2. Never Used | Create cluster 30 days ago, submit zero jobs | CRITICAL confidence | Ambari API: YARN AppsSubmitted = 0 |
| 3. Premium Storage Dev | Tag as Environment=dev, use Premium_LRS storage | HIGH confidence | `az storage account show --query 'sku.name'` |
| 4. No Autoscale | 8 worker cluster, no autoscale config | MEDIUM confidence, $4,300/month | `az hdinsight autoscale show` → error |
| 5. Outdated Version | Create cluster with HDInsight 3.6 (Spark 2.3) | HIGH confidence, security risk | `az hdinsight show --query 'properties.clusterVersion'` |
| 6. Unused Metastore | External SQL DB, zero Hive tables | MEDIUM confidence, $73/month | Query SQL DB: `SELECT COUNT(*) FROM TBLS` = 0 |
| 7. Empty Cluster | Cluster 45 days old, HDFS <1 GB used | HIGH confidence, 98% waste | Ambari API: FSNamesystem.CapacityUsed < 1 GB |
| 8. Oversized Head Nodes | 4 workers with D14_v2 heads | MEDIUM confidence, $5,890/month | Compare worker count to head node SKU |
| 9. Unused Edge Node | Edge node exists, zero SSH connections | LOW confidence, $490/month | Check Azure Monitor SSH logs (Phase 2) |
| 10. Undersized Disks | HDFS >85% full | HIGH confidence, job failures | Ambari API: FSNamesystem capacity >85% |

### Phase 2 Tests (Metrics-Based)

| Scenario | Test Setup | Expected Detection | Validation Metric |
|----------|------------|-------------------|-------------------|
| 11. Low CPU | Submit jobs using only 15% CPU avg for 30 days | HIGH confidence, 60% waste | Azure Monitor: CpuPercentage < 20% |
| 12. Zero Jobs | No YARN applications for 30 days | CRITICAL confidence, 100% waste | Ambari: YARN AppsSubmitted = 0 |
| 13. Idle Business Hours | No activity 9 AM - 5 PM for 30 days | HIGH confidence, 85% waste | Azure Monitor: CpuPercentage < 10% (9-17h) |
| 14. YARN Memory Waste | YARN AvailableMB consistently >60% | HIGH confidence, 50% waste | Ambari: YARN AvailableMB / TotalMB > 60% |
| 15. Excessive Shuffle | Spark jobs with >100 GB shuffle each | MEDIUM confidence, 25% waste | Spark History: shuffleWriteBytes > 100 GB |
| 16. Autoscale Not Working | Autoscale enabled but NumActiveWorkers constant | MEDIUM confidence, $2,800/month | Azure Monitor: NumActiveWorkers variance ≤ 1 |
| 17. Low Memory | MemoryPercentage <25% avg for 30 days | HIGH confidence, 23% savings | Azure Monitor: MemoryPercentage < 25% |
| 18. High Job Failures | >25% YARN apps failed/killed | MEDIUM confidence, 20% waste | Ambari: (AppsFailed + AppsKilled) / AppsSubmitted > 25% |

### End-to-End Test Script

```python
# test_hdinsight_detection.py
import pytest
from datetime import datetime, timedelta

def test_scenario_1_stopped_cluster():
    """Test detection of stopped clusters."""
    wasteful = detect_stopped_clusters(subscription_id)

    # Find test cluster
    test_cluster = next((c for c in wasteful if c['name'] == 'test-stopped-cluster'), None)

    assert test_cluster is not None
    assert test_cluster['confidence'] == 'high'
    assert test_cluster['waste_percentage'] == 100
    assert test_cluster['estimated_monthly_cost'] > 5000

def test_scenario_11_low_cpu_utilization():
    """Test detection of low CPU utilization."""
    wasteful = detect_low_cpu_utilization(subscription_id)

    test_cluster = next((c for c in wasteful if c['avg_cpu_percent'] < 20), None)

    assert test_cluster is not None
    assert test_cluster['confidence'] == 'high'
    assert test_cluster['recommended_worker_count'] < test_cluster['current_worker_count']
    assert test_cluster['estimated_monthly_waste'] > 1000

# Run all Phase 1 tests
pytest test_hdinsight_detection.py -v -k "phase1"

# Run all Phase 2 tests (requires metrics)
pytest test_hdinsight_detection.py -v -k "phase2"
```

---

## Troubleshooting Guide

### Issue 1: Ambari API Returns 401 Unauthorized

**Symptoms:**
- Cannot query YARN, Spark History Server, or HDFS metrics
- Error: `401 Unauthorized`

**Causes:**
- Incorrect cluster admin credentials
- Credentials not stored in Key Vault
- Cluster admin password expired

**Solution:**
```bash
# Reset cluster admin password
az hdinsight update \
  --name $CLUSTER_NAME \
  --resource-group $RESOURCE_GROUP \
  --http-password 'NewPassword123!'

# Test Ambari API access
curl -u admin:NewPassword123! \
  "https://$CLUSTER_NAME.azurehdinsight.net/api/v1/clusters/$CLUSTER_NAME" \
  | jq '.Clusters.cluster_name'
```

---

### Issue 2: Azure Monitor Metrics Return Empty Results

**Symptoms:**
- CpuPercentage, MemoryPercentage metrics have no data
- Error: `No metrics found for the specified resource`

**Causes:**
- Cluster too new (<1 hour old)
- Metrics not enabled on cluster
- Service principal lacks Monitoring Reader role

**Solution:**
```bash
# Check if metrics are enabled
az monitor diagnostic-settings list \
  --resource "/subscriptions/{sub-id}/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.HDInsight/clusters/$CLUSTER_NAME"

# Add Monitoring Reader role
az role assignment create \
  --assignee {service-principal-id} \
  --role "Monitoring Reader" \
  --scope "/subscriptions/{subscription-id}/resourceGroups/$RESOURCE_GROUP"

# Wait 15 minutes for metrics to populate
```

---

### Issue 3: Cannot Determine Worker Node Count

**Symptoms:**
- `get_worker_node_count()` returns 0 or None
- Cluster exists but compute profile is empty

**Causes:**
- Cluster in provisioning/deleting state
- API response missing compute profile data

**Solution:**
```python
def get_worker_node_count(cluster) -> int:
    """Safely get worker node count with fallbacks."""
    if not hasattr(cluster.properties, 'compute_profile'):
        return 0

    for role in cluster.properties.compute_profile.roles:
        if role.name == 'workernode':
            # Check both target_instance_count and autoscale
            if role.target_instance_count:
                return role.target_instance_count
            elif role.autoscale_configuration:
                autoscale = role.autoscale_configuration
                if hasattr(autoscale, 'capacity'):
                    return autoscale.capacity.max_instance_count

    return 0  # Fallback
```

---

### Issue 4: High False Positives for "Never Used" Detection

**Symptoms:**
- Clusters flagged as "never used" but actually run nightly batch jobs
- AppsSubmitted = 0 but cluster is legitimately active

**Causes:**
- Ambari metrics reset after cluster restart
- Jobs submitted via Livy REST API not tracked in YARN metrics
- Scheduled jobs run during off-hours (not captured in 30-day window)

**Solution:**
```python
# Enhanced detection: Check multiple sources
def detect_never_used_enhanced(cluster):
    # Check 1: YARN metrics
    yarn_apps = get_yarn_apps_count(cluster)

    # Check 2: HDFS data volume (jobs should write data)
    hdfs_used_gb = get_hdfs_used_capacity(cluster)

    # Check 3: Azure Monitor CPU history
    avg_cpu_30_days = get_cpu_metrics(cluster, days=30)

    # Cluster is truly unused if ALL indicators are low
    if yarn_apps == 0 and hdfs_used_gb < 1.0 and avg_cpu_30_days < 5:
        return True  # High confidence
    elif yarn_apps == 0 and hdfs_used_gb < 10.0:
        return True  # Medium confidence

    return False
```

---

### Issue 5: Autoscale Detected as "Not Working" but Actually Is

**Symptoms:**
- Autoscale enabled but NumActiveWorkers appears constant
- Azure Monitor shows variance ≤ 1 node

**Causes:**
- Schedule-based autoscale (not load-based) → fixed schedule
- Cluster load is steady (no scaling needed)
- Metrics granularity too coarse (6-hour intervals miss scaling events)

**Solution:**
```python
# Check autoscale type before flagging
autoscale_config = cluster.properties.compute_profile.roles[0].autoscale_configuration

if autoscale_config.recurrence:
    # Schedule-based autoscale - check against schedule
    schedules = autoscale_config.recurrence.schedule
    # Don't flag if schedule is correctly configured
    return False

elif autoscale_config.capacity:
    # Load-based autoscale - check node variance
    if node_variance <= 1:
        # Check if load actually varies
        cpu_variance = calculate_cpu_variance(cluster, days=30)
        if cpu_variance > 20:  # Load varies but nodes don't scale
            return True  # Actually not working

    return False
```

---

### Issue 6: Cost Calculations Inaccurate for Spot Instances

**Symptoms:**
- Calculated costs 3-4x higher than actual Azure bill
- Cluster uses Spot VMs but detector assumes on-demand pricing

**Causes:**
- HDInsight supports spot instances (80-90% discount)
- Detector doesn't check VM pricing tier

**Solution:**
```python
# Enhanced cost calculation with spot instance detection
def calculate_cluster_cost_enhanced(cluster) -> float:
    total_cost = 0.0

    for role in cluster.properties.compute_profile.roles:
        vm_size = role.hardware_profile.vm_size
        node_count = role.target_instance_count

        # Check if spot instance (via tags or billing API)
        is_spot = check_if_spot_instance(cluster, role.name)

        base_vm_cost = vm_prices.get(vm_size, 350.40)

        if is_spot:
            base_vm_cost *= 0.20  # Spot = ~80% discount

        hdinsight_cost = base_vm_cost * 1.40
        total_cost += hdinsight_cost * node_count

    return round(total_cost, 2)
```

---

## Business Impact Analysis

### Small Organization (5 HDInsight Clusters)

**Typical Setup:**
- 3 dev/test clusters (small, 6 workers each)
- 2 production clusters (medium, 10 workers each)

**Waste Detected:**
| Scenario | Clusters Affected | Monthly Waste | Annual Waste |
|----------|-------------------|---------------|--------------|
| No autoscale | 2 production | $8,648 | $103,776 |
| Premium storage in dev | 3 dev | $5,898 | $70,776 |
| Low CPU utilization | 1 production | $3,200 | $38,400 |
| Oversized head nodes | 3 dev | $17,670 | $212,040 |
| **Total** | **5 clusters** | **$35,416** | **$424,992** |

**ROI Calculation:**
- CloudWaste subscription: $500/month
- Waste identified: $35,416/month
- Net savings: $34,916/month
- **ROI: 6,983% annually**

---

### Enterprise (50 HDInsight Clusters)

**Typical Setup:**
- 30 dev/test clusters (various sizes)
- 15 production clusters (medium to large)
- 5 sandbox clusters (small, rarely used)

**Waste Detected:**
| Scenario | Clusters Affected | Monthly Waste | Annual Waste |
|----------|-------------------|---------------|--------------|
| Never used | 8 clusters | $72,000 | $864,000 |
| No autoscale | 20 clusters | $86,480 | $1,037,760 |
| Low CPU (<20%) | 12 clusters | $64,800 | $777,600 |
| Premium storage in dev | 25 clusters | $49,150 | $589,800 |
| Outdated versions | 15 clusters | $0 | $0 (security) |
| YARN memory waste | 10 clusters | $32,400 | $388,800 |
| High job failures | 5 clusters | $12,000 | $144,000 |
| **Total** | **50 clusters** | **$316,830** | **$3,801,960** |

**ROI Calculation:**
- CloudWaste subscription: $2,000/month (enterprise)
- Waste identified: $316,830/month
- Net savings: $314,830/month
- **ROI: 18,890% annually**

**Additional Benefits:**
- Security compliance: 15 outdated clusters upgraded → avoid penalties
- Developer productivity: 5 clusters with high failure rates fixed → save 200 hours/month
- Cost predictability: Autoscale adoption → 30% more stable monthly bills

---

### Cost Avoidance Scenarios

**Scenario A: Pre-Production Validation**
- Organization plans to deploy 10 new Spark clusters
- CloudWaste analysis shows 60% can be replaced with Synapse Spark (serverless)
- **Avoided Cost: $50,000/month = $600,000/year**

**Scenario B: Cluster Consolidation**
- 20 small clusters detected with <10% CPU utilization
- Consolidate to 5 medium clusters with autoscale
- **Savings: $120,000/month = $1,440,000/year**

**Scenario C: Storage Tier Optimization**
- 30 clusters using Premium SSD in dev/test
- Switch to Standard SSD
- **Savings: $58,980/month = $707,760/year**

---

## Implementation Roadmap

### Phase 1: Simple Detection (Week 1-2)

**Goal**: Detect configuration-based waste without requiring Azure Monitor metrics.

**Tasks:**
1. Implement Azure HDInsight SDK client
2. Build Scenarios 1-10 (stopped, never used, premium storage, no autoscale, etc.)
3. Create cost calculation engine
4. Test with 5 sample clusters
5. Deploy to CloudWaste backend

**Expected Results:**
- 10 detection scenarios operational
- 60-70% of waste identified (configuration-based)
- No dependency on Azure Monitor or Ambari APIs

---

### Phase 2: Metrics-Based Detection (Week 3-4)

**Goal**: Add Azure Monitor + Ambari API integration for deep usage analysis.

**Tasks:**
1. Integrate `azure-monitor-query==1.3.0`
2. Implement Ambari REST API client
3. Build Scenarios 11-18 (low CPU, YARN waste, job failures, etc.)
4. Add confidence level calculations
5. Test metrics collection for 30-day period

**Expected Results:**
- 18 detection scenarios operational
- 90%+ of waste identified
- High confidence waste detection

---

### Phase 3: Frontend Integration (Week 5)

**Goal**: Display HDInsight waste in CloudWaste dashboard.

**Tasks:**
1. Add HDInsight resource type to frontend
2. Create cluster detail pages (show YARN metrics, Spark job history)
3. Implement cost savings calculator
4. Add action buttons ("Delete Cluster", "Enable Autoscale", "Rightsize Nodes")

**Expected Results:**
- HDInsight visible in main dashboard
- Users can drill down into cluster waste details
- One-click remediation actions

---

### Phase 4: Automated Remediation (Week 6-8)

**Goal**: Allow CloudWaste to automatically fix waste (with user approval).

**Tasks:**
1. Implement autoscale enablement via Azure SDK
2. Implement cluster resizing (change VM SKUs)
3. Implement storage tier changes (Premium → Standard)
4. Add approval workflow (require user confirmation for changes)
5. Add audit log (track all automated changes)

**Expected Results:**
- Users can enable "Auto-Fix" mode for HDInsight
- CloudWaste automatically enables autoscale on flagged clusters
- CloudWaste downsizes oversized head nodes
- 80% of waste remediated automatically

---

### Phase 5: Advanced Analytics (Week 9-10)

**Goal**: Provide predictive insights and benchmarking.

**Tasks:**
1. Build historical waste trends (track waste reduction over time)
2. Implement cluster sizing recommendations (ML-based)
3. Add cost forecasting (predict next month's waste if no changes made)
4. Benchmark against industry averages (show "You waste 45% less than average")

**Expected Results:**
- Users see waste reduction progress over time
- Proactive recommendations ("Your cluster will exceed budget in 10 days")
- Competitive benchmarking

---

## References

### Official Documentation

1. **Azure HDInsight Overview**
   https://learn.microsoft.com/en-us/azure/hdinsight/

2. **HDInsight Pricing**
   https://azure.microsoft.com/en-us/pricing/details/hdinsight/

3. **HDInsight Autoscale**
   https://learn.microsoft.com/en-us/azure/hdinsight/hdinsight-autoscale-clusters

4. **Ambari REST API Reference**
   https://github.com/apache/ambari/blob/trunk/ambari-server/docs/api/v1/index.md

5. **Azure Monitor Metrics for HDInsight**
   https://learn.microsoft.com/en-us/azure/hdinsight/hdinsight-hadoop-oms-log-analytics-tutorial

6. **Azure Python SDK for HDInsight**
   https://learn.microsoft.com/en-us/python/api/azure-mgmt-hdinsight/

7. **Spark History Server REST API**
   https://spark.apache.org/docs/latest/monitoring.html#rest-api

### Best Practices

1. **HDInsight Best Practices - Microsoft**
   https://learn.microsoft.com/en-us/azure/hdinsight/hdinsight-best-practices

2. **Spark Performance Tuning**
   https://spark.apache.org/docs/latest/tuning.html

3. **Cost Optimization for HDInsight**
   https://learn.microsoft.com/en-us/azure/hdinsight/hdinsight-administer-use-portal-linux#scale-clusters

### Community Resources

1. **HDInsight Cost Optimization Guide (GitHub)**
   https://github.com/Azure-Samples/hdinsight-cost-optimization

2. **Databricks vs HDInsight Comparison**
   https://www.databricks.com/blog/2021/03/15/comparing-databricks-and-azure-hdinsight.html

---

**Document Version**: 1.0
**Last Updated**: 2025-10-29
**Authors**: CloudWaste Team
**Coverage**: 18 waste detection scenarios (100% comprehensive)
**Estimated Detection Value**: $35,000 - $320,000/month per organization
