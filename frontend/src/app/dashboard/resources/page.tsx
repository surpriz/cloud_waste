"use client";

import { useEffect, useState } from "react";
import { useResourceStore } from "@/stores/useResourceStore";
import { useAccountStore } from "@/stores/useAccountStore";
import { useOnboardingStore } from "@/stores/useOnboardingStore";
import {
  Filter,
  RefreshCw,
  Eye,
  EyeOff,
  Trash2,
  DollarSign,
  HardDrive,
  Wifi,
  Camera,
  Server,
  Network,
  Database,
  Zap,
  Activity,
  AlertTriangle,
  TrendingDown,
  Users,
  Clock,
  FileText,
  Cpu,
} from "lucide-react";
import type { ResourceStatus, ResourceType } from "@/types";
import { ResourceChartsSection } from "@/components/dashboard/ResourceChartsSection";

const resourceIcons: Record<ResourceType, any> = {
  // AWS Resources
  ebs_volume: HardDrive,
  elastic_ip: Wifi,
  ebs_snapshot: Camera,
  ec2_instance: Server,
  load_balancer: Network,
  rds_instance: Database,
  nat_gateway: Network,
  fsx_file_system: HardDrive,
  neptune_cluster: Database,
  msk_cluster: Server,
  eks_cluster: Server,
  sagemaker_endpoint: Server,
  redshift_cluster: Database,
  elasticache_cluster: Database,
  vpn_connection: Network,
  transit_gateway_attachment: Network,
  opensearch_domain: Database,
  global_accelerator: Network,
  kinesis_stream: Server,
  vpc_endpoint: Network,
  documentdb_cluster: Database,
  s3_bucket: HardDrive,
  lambda_function: Zap,
  dynamodb_table: Database,
  api_gateway: Network,
  cloudfront_distribution: Network,
  ecs_cluster: Server,
  cloudwatch_log_group: FileText,
  // Azure Resources
  managed_disk_unattached: HardDrive,
  public_ip_unassociated: Wifi,
  disk_snapshot_orphaned: Camera,
  virtual_machine_deallocated: Server,
  // Azure Phase 1 - Advanced waste scenarios
  managed_disk_on_stopped_vm: HardDrive,
  public_ip_on_stopped_resource: Wifi,
  // Azure VM Phase A - Virtual Machine waste scenarios
  virtual_machine_stopped_not_deallocated: Server,
  virtual_machine_never_started: Server,
  virtual_machine_oversized_premium: Server,
  virtual_machine_untagged_orphan: Server,
  // Azure Storage Accounts
  storage_account_empty: HardDrive,
  storage_account_never_used: HardDrive,
  storage_account_no_transactions: HardDrive,
  // Azure Container Apps - Phase 1 (10 scenarios)
  container_app_stopped: Server,
  container_app_zero_replicas: Server,
  container_app_unnecessary_premium_tier: Server,
  container_app_dev_zone_redundancy: Server,
  container_app_no_ingress_configured: Server,
  container_app_empty_environment: Server,
  container_app_unused_revision: Server,
  container_app_overprovisioned_cpu_memory: Server,
  container_app_custom_domain_unused: Server,
  container_app_secrets_unused: Server,
  // Azure Container Apps - Phase 2 (6 scenarios with Azure Monitor)
  container_app_low_cpu_utilization: Server,
  container_app_low_memory_utilization: Server,
  container_app_zero_http_requests: Server,
  container_app_high_replica_low_traffic: Server,
  container_app_autoscaling_not_triggering: Server,
  container_app_cold_start_issues: Server,
  // Azure Virtual Desktop - Phase 1 (12 scenarios)
  avd_host_pool_empty: Server,
  avd_session_host_stopped: Server,
  avd_session_host_never_used: Server,
  avd_host_pool_no_autoscale: Server,
  avd_host_pool_over_provisioned: Server,
  avd_application_group_empty: Server,
  avd_workspace_empty: Server,
  avd_premium_disk_in_dev: HardDrive,
  avd_unnecessary_availability_zones: Network,
  avd_personal_desktop_never_used: Server,
  avd_fslogix_oversized: HardDrive,
  avd_session_host_old_vm_generation: Server,
  // Azure Virtual Desktop - Phase 2 (6 scenarios with Azure Monitor)
  avd_low_cpu_utilization: Server,
  avd_low_memory_utilization: Server,
  avd_zero_user_sessions: Server,
  avd_high_host_count_low_users: Server,
  avd_disconnected_sessions_waste: Server,
  avd_peak_hours_mismatch: Server,
  // Azure HDInsight Spark Cluster - Phase 1 (10 scenarios)
  hdinsight_spark_cluster_stopped: Server,
  hdinsight_spark_cluster_never_used: Server,
  hdinsight_spark_premium_storage_dev: HardDrive,
  hdinsight_spark_no_autoscale: Server,
  hdinsight_spark_outdated_version: Server,
  hdinsight_spark_external_metastore_unused: Database,
  hdinsight_spark_empty_cluster: Server,
  hdinsight_spark_oversized_head_nodes: Server,
  hdinsight_spark_unnecessary_edge_node: Server,
  hdinsight_spark_undersized_disks: HardDrive,
  // Azure HDInsight Spark Cluster - Phase 2 (8 scenarios with Azure Monitor + Ambari)
  hdinsight_spark_low_cpu_utilization: Server,
  hdinsight_spark_zero_jobs_metrics: Server,
  hdinsight_spark_idle_business_hours: Server,
  hdinsight_spark_high_yarn_memory_waste: Server,
  hdinsight_spark_excessive_shuffle_data: Server,
  hdinsight_spark_autoscale_not_working: Server,
  hdinsight_spark_low_memory_utilization: Server,
  hdinsight_spark_high_job_failure_rate: Server,
  // Azure Machine Learning Compute Instance - Phase 1 (10 scenarios)
  ml_compute_instance_no_auto_shutdown: Server,
  ml_compute_instance_gpu_for_cpu_workload: Cpu,
  ml_compute_instance_stopped_30_days: Server,
  ml_compute_instance_over_provisioned: TrendingDown,
  ml_compute_instance_never_accessed: AlertTriangle,
  ml_compute_instance_multiple_per_user: Users,
  ml_compute_instance_premium_ssd_unnecessary: HardDrive,
  ml_compute_instance_no_idle_shutdown: Clock,
  ml_compute_instance_dev_high_performance_sku: Zap,
  ml_compute_instance_old_sdk_deprecated_image: AlertTriangle,
  // Azure Machine Learning Compute Instance - Phase 2 (8 scenarios)
  ml_compute_instance_low_cpu_utilization: Activity,
  ml_compute_instance_low_gpu_utilization: Cpu,
  ml_compute_instance_idle_business_hours: Clock,
  ml_compute_instance_no_jupyter_activity: FileText,
  ml_compute_instance_no_training_jobs: Activity,
  ml_compute_instance_low_memory_utilization: Server,
  ml_compute_instance_network_idle: Network,
  ml_compute_instance_disk_io_near_zero: HardDrive,
  // Azure App Service (Web Apps) - Phase 1 (10 scenarios)
  app_service_plan_empty: Server,
  app_service_premium_in_dev: Zap,
  app_service_no_auto_scale: TrendingDown,
  app_service_always_on_low_traffic: Zap,
  app_service_unused_deployment_slots: Server,
  app_service_over_provisioned_plan: TrendingDown,
  app_service_stopped_apps_paid_plan: Server,
  app_service_multiple_plans_consolidation: Server,
  app_service_vnet_integration_unused: Network,
  app_service_old_runtime_version: AlertTriangle,
  // Azure App Service (Web Apps) - Phase 2 (8 scenarios)
  app_service_low_cpu_utilization: Activity,
  app_service_low_memory_utilization: Server,
  app_service_low_request_count: Activity,
  app_service_no_traffic_business_hours: Clock,
  app_service_high_http_error_rate: AlertTriangle,
  app_service_slow_response_time: Clock,
  app_service_auto_scale_never_triggers: TrendingDown,
  app_service_cold_start_excessive: Clock,
  // Azure Networking (ExpressRoute, VPN, NICs) - 8 scenarios
  expressroute_circuit_not_provisioned: Network,
  expressroute_circuit_no_connection: Network,
  expressroute_gateway_orphaned: Network,
  expressroute_circuit_underutilized: TrendingDown,
  vpn_gateway_disconnected: Network,
  vpn_gateway_basic_sku_deprecated: AlertTriangle,
  vpn_gateway_no_connections: Network,
  network_interface_orphaned: Network,
  // GCP Resources
  gce_instance_stopped: Server,
  gce_instance_idle: Server,
  gke_cluster_idle: Server,
  persistent_disk_unattached: HardDrive,
  gcs_bucket_empty: HardDrive,
  disk_snapshot_old: Camera,
  static_ip_unattached: Wifi,
  nat_gateway_unused: Network,
  cloud_sql_stopped: Database,
  cloud_sql_idle: Database,
};

// Confidence level badge component
const ConfidenceLevelBadge = ({ level }: { level?: string }) => {
  if (!level) return null;

  const config = {
    critical: {
      emoji: '🔴',
      label: 'Critical',
      bgColor: 'bg-red-100',
      textColor: 'text-red-800',
      borderColor: 'border-red-300',
    },
    high: {
      emoji: '🟠',
      label: 'High',
      bgColor: 'bg-orange-100',
      textColor: 'text-orange-800',
      borderColor: 'border-orange-300',
    },
    medium: {
      emoji: '🟡',
      label: 'Medium',
      bgColor: 'bg-yellow-100',
      textColor: 'text-yellow-800',
      borderColor: 'border-yellow-300',
    },
    low: {
      emoji: '🟢',
      label: 'Low',
      bgColor: 'bg-green-100',
      textColor: 'text-green-800',
      borderColor: 'border-green-300',
    },
  };

  const conf = config[level as keyof typeof config] || config.low;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${conf.bgColor} ${conf.textColor} ${conf.borderColor}`}>
      <span>{conf.emoji}</span>
      <span>{conf.label}</span>
    </span>
  );
};

export default function ResourcesPage() {
  const {
    resources,
    stats,
    fetchResources,
    fetchStats,
    updateResource,
    deleteResource,
    filters,
    setFilters,
    isLoading,
  } = useResourceStore();
  const { accounts, fetchAccounts } = useAccountStore();

  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchAccounts();
    fetchResources();
    fetchStats();
  }, [fetchAccounts, fetchResources, fetchStats]);

  // Mark results as reviewed when user visits this page
  useEffect(() => {
    useOnboardingStore.getState().setResultsReviewed(true);
  }, []);

  const handleFilterChange = (key: string, value: any) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    fetchResources(newFilters);
  };

  const handleIgnore = async (resourceId: string) => {
    try {
      await updateResource(resourceId, { status: "ignored" });
      fetchResources();
      fetchStats();
    } catch (err) {
      // Error handled by store
    }
  };

  const handleMarkForDeletion = async (resourceId: string) => {
    try {
      await updateResource(resourceId, { status: "marked_for_deletion" });
      fetchResources();
      fetchStats();
    } catch (err) {
      // Error handled by store
    }
  };

  const handleDelete = async (resourceId: string) => {
    if (!confirm("Delete this resource record? This will NOT delete the actual AWS resource.")) {
      return;
    }
    try {
      await deleteResource(resourceId);
      fetchResources();
      fetchStats();
    } catch (err) {
      // Error handled by store
    }
  };

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 flex items-center gap-2">
            <span className="text-3xl">💸</span> Waste Detection
          </h1>
          <p className="mt-1 md:mt-2 text-sm md:text-base text-gray-600">
            Resources wasting money unnecessarily - take immediate action to delete or ignore them
          </p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
        >
          <Filter className="h-5 w-5" />
          Filters
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Resources"
            value={stats.total_resources}
            icon={Server}
            color="blue"
          />
          <StatCard
            title="Active"
            value={stats.by_status?.active || 0}
            icon={Eye}
            color="green"
          />
          <StatCard
            title="Monthly Cost"
            value={`$${stats.total_monthly_cost.toFixed(2)}`}
            icon={DollarSign}
            color="orange"
          />
          <StatCard
            title="Annual Cost"
            value={`$${stats.total_annual_cost.toFixed(2)}`}
            icon={DollarSign}
            color="red"
          />
        </div>
      )}

      {/* Visual Overview Charts */}
      <ResourceChartsSection
        resources={resources}
        stats={stats}
      />

      {/* Filters */}
      {showFilters && (
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-gray-900">Filters</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Account
              </label>
              <select
                value={filters.cloud_account_id || ""}
                onChange={(e) =>
                  handleFilterChange("cloud_account_id", e.target.value || undefined)
                }
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">All Accounts</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.account_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Resource Type
              </label>
              <select
                value={filters.resource_type || ""}
                onChange={(e) =>
                  handleFilterChange("resource_type", e.target.value || undefined)
                }
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">All Types</option>
                <optgroup label="🟠 AWS - Storage & Compute">
                  <option value="ebs_volume">EBS Volume</option>
                  <option value="ebs_snapshot">EBS Snapshot</option>
                  <option value="ec2_instance">EC2 Instance</option>
                  <option value="fsx_file_system">FSx File System</option>
                  <option value="lambda_function">Lambda Function</option>
                  <option value="s3_bucket">S3 Bucket</option>
                </optgroup>
                <optgroup label="🟠 AWS - Database">
                  <option value="dynamodb_table">DynamoDB Table</option>
                  <option value="rds_instance">RDS Instance</option>
                  <option value="neptune_cluster">Neptune Cluster</option>
                  <option value="redshift_cluster">Redshift Cluster</option>
                  <option value="documentdb_cluster">DocumentDB Cluster</option>
                  <option value="elasticache_cluster">ElastiCache Cluster</option>
                  <option value="opensearch_domain">OpenSearch Domain</option>
                </optgroup>
                <optgroup label="🟠 AWS - Networking">
                  <option value="elastic_ip">Elastic IP</option>
                  <option value="nat_gateway">NAT Gateway</option>
                  <option value="load_balancer">Load Balancer</option>
                  <option value="vpn_connection">VPN Connection</option>
                  <option value="transit_gateway_attachment">Transit Gateway Attachment</option>
                  <option value="vpc_endpoint">VPC Endpoint</option>
                  <option value="global_accelerator">Global Accelerator</option>
                </optgroup>
                <optgroup label="🟠 AWS - Containers & Streaming">
                  <option value="eks_cluster">EKS Cluster</option>
                  <option value="msk_cluster">MSK Cluster</option>
                  <option value="kinesis_stream">Kinesis Stream</option>
                </optgroup>
                <optgroup label="🟠 AWS - Machine Learning">
                  <option value="sagemaker_endpoint">SageMaker Endpoint</option>
                </optgroup>
                <optgroup label="🔵 Azure - Storage & Compute">
                  <option value="managed_disk_unattached">Managed Disk (Unattached)</option>
                  <option value="managed_disk_on_stopped_vm">Managed Disk (On Stopped VM)</option>
                  <option value="disk_snapshot_orphaned">Disk Snapshot (Orphaned)</option>
                  <option value="virtual_machine_deallocated">Virtual Machine (Deallocated)</option>
                </optgroup>
                <optgroup label="🔵 Azure - Networking">
                  <option value="public_ip_unassociated">Public IP (Unassociated)</option>
                  <option value="public_ip_on_stopped_resource">Public IP (On Stopped Resource)</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Status
              </label>
              <select
                value={filters.status || ""}
                onChange={(e) =>
                  handleFilterChange("status", e.target.value || undefined)
                }
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
              >
                <option value="">All Statuses</option>
                <option value="active">Active</option>
                <option value="ignored">Ignored</option>
                <option value="marked_for_deletion">Marked for Deletion</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Resources List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : resources.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">
            No resources found
          </h3>
          <p className="mt-2 text-gray-600">
            Run a scan to detect orphaned resources
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {resources.map((resource) => (
            <ResourceCard
              key={resource.id}
              resource={resource}
              onIgnore={() => handleIgnore(resource.id)}
              onMarkForDeletion={() => handleMarkForDeletion(resource.id)}
              onDelete={() => handleDelete(resource.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ title, value, icon: Icon, color }: any) {
  const colors: any = {
    blue: "bg-blue-100 text-blue-600",
    green: "bg-green-100 text-green-600",
    red: "bg-red-100 text-red-600",
    orange: "bg-orange-100 text-orange-600",
  };

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{value}</p>
        </div>
        <div className={`rounded-lg p-3 ${colors[color]}`}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}

function ResourceCard({ resource, onIgnore, onMarkForDeletion, onDelete }: any) {
  const ResourceIcon = resourceIcons[resource.resource_type as ResourceType] || Server;
  const [expanded, setExpanded] = useState(false);

  const statusColors: any = {
    active: "bg-green-100 text-green-700",
    ignored: "bg-gray-100 text-gray-700",
    marked_for_deletion: "bg-red-100 text-red-700",
  };

  // Calculate cumulative cost lost since creation
  const ageDays = resource.resource_metadata?.age_days;
  const dailyCost = resource.estimated_monthly_cost / 30;

  // Show cost even for resources less than 1 day old (age_days = 0)
  // Calculate based on created_at timestamp if age_days is 0
  let cumulativeCost = null;
  let displayAge = "";

  if (ageDays !== undefined && ageDays >= 0) {
    if (ageDays > 0) {
      // 1+ days old
      cumulativeCost = dailyCost * ageDays;
      displayAge = `${ageDays} day${ageDays !== 1 ? 's' : ''}`;
    } else if (ageDays === 0 && resource.resource_metadata?.created_at) {
      // Less than 24h old - calculate hours
      try {
        // Parse ISO date - replace +00:00 with Z for better compatibility
        const dateString = resource.resource_metadata.created_at.replace('+00:00', 'Z');
        const createdAt = new Date(dateString);
        const now = new Date();

        // Validate the date is valid
        if (!isNaN(createdAt.getTime())) {
          const ageHours = Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60 * 60));

          if (ageHours > 0) {
            const hourlyCost = dailyCost / 24;
            cumulativeCost = hourlyCost * ageHours;
            displayAge = `${ageHours} hour${ageHours !== 1 ? 's' : ''}`;
          } else if (ageHours === 0) {
            // Show "less than 1 hour" for very recent resources
            displayAge = "less than 1 hour";
            cumulativeCost = 0.01; // Minimum to show
          }
        }
      } catch (e) {
        // Silently ignore date parsing errors
      }
    }
  }

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex flex-1 items-start gap-4">
          <div className="rounded-lg bg-blue-100 p-3">
            <ResourceIcon className="h-6 w-6 text-blue-600" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h3 className="font-semibold text-gray-900">
                {resource.resource_name || resource.resource_id}
              </h3>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  statusColors[resource.status]
                }`}
              >
                {resource.status.replace("_", " ").toUpperCase()}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-600">
              {resource.resource_type.replace(/_/g, " ").toUpperCase()} · {resource.region}
            </p>
            <div className="mt-2 flex flex-col gap-2">
              <div className="flex items-center justify-between gap-2 text-sm text-gray-500">
                <span>ID: {resource.resource_id}</span>
                {/* Confidence Level Badge */}
                <ConfidenceLevelBadge level={resource.resource_metadata?.confidence_level} />
              </div>

              {/* Orphan reason - why is this resource orphaned? */}
              {(resource.resource_metadata?.orphan_reason || resource.resource_metadata?.why_orphaned) && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-2">
                  <div className="flex items-start gap-2">
                    <span className="text-amber-700 font-medium text-sm">⚠️ Why is this orphaned?</span>
                    {resource.resource_metadata?.confidence && (
                      <span className={`ml-auto px-2 py-0.5 rounded text-xs font-semibold ${
                        resource.resource_metadata.confidence === 'high'
                          ? 'bg-red-100 text-red-700'
                          : resource.resource_metadata.confidence === 'medium'
                          ? 'bg-orange-100 text-orange-700'
                          : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {resource.resource_metadata.confidence} confidence
                      </span>
                    )}
                  </div>

                  {/* EBS Volume specific criteria */}
                  {resource.resource_type === 'ebs_volume' && (
                    <div className="space-y-1 text-sm">
                      {/* Check if volume is attached or unattached */}
                      {resource.resource_metadata?.is_attached ? (
                        <>
                          {/* ATTACHED but unused volume */}
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">⚠️</span>
                            <span>
                              Attached to EC2 instance{' '}
                              <code className="bg-orange-100 px-1 rounded text-xs">
                                {resource.resource_metadata?.attached_instance_id}
                              </code>
                            </span>
                          </div>
                          {resource.resource_metadata?.orphan_type === 'attached_never_used' && (
                            <div className="flex items-center gap-2 text-red-700">
                              <span className="font-semibold">✗</span>
                              <span>Never used since creation ({resource.resource_metadata?.age_days} days ago)</span>
                            </div>
                          )}
                          {resource.resource_metadata?.orphan_type === 'attached_idle' && (
                            <>
                              <div className="flex items-center gap-2 text-red-700">
                                <span className="font-semibold">✗</span>
                                <span>
                                  No I/O activity for {resource.resource_metadata?.usage_history?.days_since_last_use} days
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-red-700">
                                <span className="font-semibold">✗</span>
                                <span>Volume is idle (likely unused secondary storage)</span>
                              </div>
                            </>
                          )}
                          {resource.resource_metadata?.usage_history?.total_read_ops === 0 &&
                           resource.resource_metadata?.usage_history?.total_write_ops === 0 && (
                            <div className="flex items-center gap-2 text-red-700">
                              <span className="font-semibold">✗</span>
                              <span>0 read/write operations detected</span>
                            </div>
                          )}
                        </>
                      ) : (
                        <>
                          {/* UNATTACHED volume */}
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Not attached to any EC2 instance (status: available)</span>
                          </div>
                          {resource.resource_metadata?.usage_history?.total_read_ops === 0 &&
                           resource.resource_metadata?.usage_history?.total_write_ops === 0 && (
                            <div className="flex items-center gap-2 text-red-700">
                              <span className="font-semibold">✗</span>
                              <span>No I/O activity detected (0 read/write operations)</span>
                            </div>
                          )}
                          {resource.resource_metadata?.usage_history?.usage_category === 'never_used' && (
                            <div className="flex items-center gap-2 text-red-700">
                              <span className="font-semibold">✗</span>
                              <span>Never used since creation</span>
                            </div>
                          )}
                          {resource.resource_metadata?.usage_history?.usage_category === 'long_abandoned' && (
                            <div className="flex items-center gap-2 text-red-700">
                              <span className="font-semibold">✗</span>
                              <span>
                                Abandoned {resource.resource_metadata?.usage_history?.days_since_last_use} days ago
                              </span>
                            </div>
                          )}
                        </>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* Elastic IP specific criteria */}
                  {resource.resource_type === 'elastic_ip' && (
                    <div className="space-y-1 text-sm">
                      {resource.resource_metadata?.orphan_type === 'unassociated' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">✗</span>
                          <span>Not associated with any instance or network interface</span>
                        </div>
                      )}
                      {resource.resource_metadata?.orphan_type === 'associated_stopped_instance' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>
                              Associated to <span className="font-semibold">STOPPED</span> instance{' '}
                              <code className="bg-red-100 px-1 rounded text-xs">
                                {resource.resource_metadata?.associated_instance_id}
                              </code>
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Elastic IP on stopped instance is charged ($3.60/month)</span>
                          </div>
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'associated_orphaned_eni' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>
                              Associated to orphaned network interface{' '}
                              <code className="bg-red-100 px-1 rounded text-xs">
                                {resource.resource_metadata?.network_interface_id}
                              </code>
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>ENI not attached to any instance (still charged)</span>
                          </div>
                        </>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* RDS Instance specific criteria */}
                  {resource.resource_type === 'rds_instance' && (
                    <div className="space-y-2 text-sm">
                      {/* Database engine info */}
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-gray-200 rounded text-xs font-semibold">
                          {resource.resource_metadata.engine?.toUpperCase()}
                        </span>
                        <span className="text-gray-600 text-xs">
                          {resource.resource_metadata.db_class} | {resource.resource_metadata.storage_gb} GB
                          {resource.resource_metadata.multi_az && ' | Multi-AZ'}
                        </span>
                      </div>

                      {/* Orphan type specific messages */}
                      {resource.resource_metadata?.orphan_type === 'stopped' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">⏸️</span>
                          <span className="font-semibold">Database stopped for {resource.resource_metadata.age_days}+ days</span>
                        </div>
                      )}

                      {resource.resource_metadata?.orphan_type === 'idle_running' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">💤</span>
                            <span className="font-semibold">Running with 0 connections for {resource.resource_metadata.age_days}+ days</span>
                          </div>
                          <div className="flex items-center gap-2 text-orange-600">
                            <span className="font-semibold">⚠️</span>
                            <span>Paying ${resource.resource_metadata.compute_cost_monthly}/month compute cost for unused database</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'never_connected' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🆕</span>
                            <span className="font-semibold">Created {resource.resource_metadata.age_days} days ago, never connected</span>
                          </div>
                          <div className="flex items-center gap-2 text-gray-600">
                            <span className="font-semibold">📊</span>
                            <span>0 database connections since creation</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'zero_io' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">📊</span>
                            <span className="font-semibold">No read/write operations in 30 days</span>
                          </div>
                          <div className="flex items-center gap-2 text-gray-600 text-xs">
                            <span>Read IOPS: {resource.resource_metadata.cloudwatch_stats?.avg_read_iops || 0} | Write IOPS: {resource.resource_metadata.cloudwatch_stats?.avg_write_iops || 0}</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'no_backups' && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">🚫</span>
                          <span className="font-semibold">No automated backups configured</span>
                        </div>
                      )}

                      {/* CloudWatch stats for running instances */}
                      {resource.resource_metadata.status === 'available' && resource.resource_metadata.cloudwatch_stats && (
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1">
                          <div className="font-semibold text-gray-700">CloudWatch Metrics (30 days avg)</div>
                          <div className="flex gap-4">
                            <span>Connections: {resource.resource_metadata.cloudwatch_stats.avg_connections}</span>
                            <span>Read IOPS: {resource.resource_metadata.cloudwatch_stats.avg_read_iops}</span>
                            <span>Write IOPS: {resource.resource_metadata.cloudwatch_stats.avg_write_iops}</span>
                          </div>
                        </div>
                      )}

                      {/* Cost breakdown */}
                      {resource.resource_metadata.compute_cost_monthly > 0 && (
                        <div className="text-xs text-gray-600">
                          💰 Compute: ${resource.resource_metadata.compute_cost_monthly}/mo + Storage: ${resource.resource_metadata.storage_cost_monthly}/mo
                        </div>
                      )}

                      {/* Backup status */}
                      {resource.resource_metadata.backup_retention_period === 0 && (
                        <div className="text-xs text-orange-600">
                          ⚠️ Backup retention: {resource.resource_metadata.backup_retention_period} days (backups disabled)
                        </div>
                      )}
                    </div>
                  )}

                  {/* EC2 Instance specific criteria */}
                  {resource.resource_type === 'ec2_instance' && (
                    <div className="space-y-1 text-sm">
                      {resource.resource_metadata?.orphan_type === 'stopped' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Instance is stopped</span>
                          </div>
                          {resource.resource_metadata?.stopped_days !== undefined && (
                            <div className="flex items-center gap-2 text-red-700">
                              <span className="font-semibold">✗</span>
                              <span>Stopped for {resource.resource_metadata.stopped_days} days</span>
                            </div>
                          )}
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'idle_running' && (
                        <>
                          <div className="flex items-center gap-2 text-blue-700">
                            <span className="font-semibold">ℹ️</span>
                            <span>Instance running with {resource.resource_metadata.avg_cpu_percent}% avg CPU and {(resource.resource_metadata.total_network_bytes / 1_000_000).toFixed(2)}MB network traffic over {resource.resource_metadata.lookback_hours || 2} hours ({resource.resource_metadata.confidence} confidence)</span>
                          </div>
                        </>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">💡</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* Load Balancer specific criteria */}
                  {resource.resource_type === 'load_balancer' && (
                    <div className="space-y-2 text-sm">
                      {/* Load Balancer Type Badge */}
                      {resource.resource_metadata?.type && (
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            resource.resource_metadata.type === 'application' ? 'bg-blue-100 text-blue-700' :
                            resource.resource_metadata.type === 'network' ? 'bg-green-100 text-green-700' :
                            resource.resource_metadata.type === 'gateway' ? 'bg-purple-100 text-purple-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {resource.resource_metadata.type.toUpperCase()}
                          </span>
                          <span className="text-gray-600">{resource.resource_metadata.type_full}</span>
                        </div>
                      )}

                      {/* Orphan type specific messages */}
                      {resource.resource_metadata?.orphan_type === 'no_listeners' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">🚫</span>
                          <span className="font-semibold">No listeners configured (unusable)</span>
                        </div>
                      )}

                      {resource.resource_metadata?.orphan_type === 'no_target_groups' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">📦</span>
                          <span className="font-semibold">No target groups attached</span>
                        </div>
                      )}

                      {resource.resource_metadata?.orphan_type === 'no_healthy_targets' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">✗</span>
                          <span className="font-semibold">No healthy backend targets</span>
                        </div>
                      )}

                      {resource.resource_metadata?.orphan_type === 'never_used' && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">🆕</span>
                          <span className="font-semibold">Never received traffic since creation</span>
                        </div>
                      )}

                      {resource.resource_metadata?.orphan_type === 'unhealthy_long_term' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">⏰</span>
                          <span className="font-semibold">All targets unhealthy for 90+ days</span>
                        </div>
                      )}

                      {resource.resource_metadata?.orphan_type === 'sg_blocks_traffic' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">🔒</span>
                          <span className="font-semibold">Security group blocks all inbound traffic</span>
                        </div>
                      )}

                      {/* Listener count */}
                      {resource.resource_metadata?.listener_count !== undefined && (
                        <div className={`flex items-center gap-2 ${resource.resource_metadata.listener_count > 0 ? 'text-green-700' : 'text-red-700'}`}>
                          <span className="font-semibold">{resource.resource_metadata.listener_count > 0 ? '✓' : '✗'}</span>
                          <span>{resource.resource_metadata.listener_count} listener(s)</span>
                        </div>
                      )}

                      {/* Target health status */}
                      {resource.resource_metadata?.healthy_target_count !== undefined && (
                        <div className={`flex items-center gap-2 ${
                          resource.resource_metadata.healthy_target_count > 0 ? 'text-green-700' : 'text-red-700'
                        }`}>
                          <span className="font-semibold">{resource.resource_metadata.healthy_target_count > 0 ? '✓' : '✗'}</span>
                          <span>
                            {resource.resource_metadata.healthy_target_count} / {resource.resource_metadata.total_target_count} healthy targets
                          </span>
                        </div>
                      )}

                      {/* Additional orphan reasons */}
                      {resource.resource_metadata?.orphan_reasons && resource.resource_metadata.orphan_reasons.length > 1 && (
                        <div className="space-y-1 ml-6">
                          {resource.resource_metadata.orphan_reasons.slice(1).map((reason: string, idx: number) => (
                            <div key={idx} className="flex items-center gap-2 text-orange-600 text-xs">
                              <span>⚠️</span>
                              <span>{reason}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Age and confidence */}
                      {resource.resource_metadata?.age_days !== undefined && (
                        <div className="flex items-center gap-2 text-gray-600">
                          <span>⏱️</span>
                          <span>Age: {resource.resource_metadata.age_days} days</span>
                          {resource.resource_metadata.confidence && (
                            <span className={`ml-2 px-2 py-0.5 rounded text-xs font-semibold ${
                              resource.resource_metadata.confidence === 'critical' ? 'bg-red-600 text-white' :
                              resource.resource_metadata.confidence === 'high' ? 'bg-red-100 text-red-700' :
                              resource.resource_metadata.confidence === 'medium' ? 'bg-orange-100 text-orange-700' :
                              'bg-yellow-100 text-yellow-700'
                            }`}>
                              {resource.resource_metadata.confidence === 'critical' ? '🚨 CRITICAL' :
                               resource.resource_metadata.confidence === 'high' ? 'High confidence' :
                               resource.resource_metadata.confidence === 'medium' ? 'Medium confidence' :
                               'Low confidence'}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* NAT Gateway specific criteria */}
                  {resource.resource_type === 'nat_gateway' && (
                    <div className="space-y-1 text-sm">
                      {/* Orphan type specific messages */}
                      {resource.resource_metadata?.orphan_type === 'no_routes' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">🚫</span>
                          <span className="font-semibold">NOT referenced in any route table</span>
                        </div>
                      )}
                      {resource.resource_metadata?.orphan_type === 'routes_not_associated' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">⚠️</span>
                            <span>Referenced in {resource.resource_metadata?.route_tables_count || 0} route table(s)</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>But route tables NOT associated with any subnet</span>
                          </div>
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'no_igw' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">🌐</span>
                          <span className="font-semibold">VPC has NO Internet Gateway (broken config)</span>
                        </div>
                      )}
                      {resource.resource_metadata?.orphan_type === 'low_traffic' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">✗</span>
                          <span>No outbound traffic detected over 30 days</span>
                        </div>
                      )}

                      {/* Traffic info */}
                      {resource.resource_metadata?.bytes_out_30d !== undefined && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">📊</span>
                          <span>Only {(resource.resource_metadata.bytes_out_30d / 1024).toFixed(2)} KB transferred in last 30 days</span>
                        </div>
                      )}

                      {/* Routing info - only show if not already displayed via orphan_type */}
                      {resource.resource_metadata?.has_routes !== undefined &&
                       resource.resource_metadata?.orphan_type !== 'no_routes' && (
                        <div className={`flex items-center gap-2 ${resource.resource_metadata.has_routes ? 'text-green-700' : 'text-red-700'}`}>
                          <span className="font-semibold">{resource.resource_metadata.has_routes ? '✓' : '✗'}</span>
                          <span>
                            {resource.resource_metadata.has_routes
                              ? `Referenced in ${resource.resource_metadata.route_tables_count || 0} route table(s)`
                              : 'Not referenced in any route table'}
                          </span>
                        </div>
                      )}

                      {/* Subnet associations */}
                      {resource.resource_metadata?.associated_subnets_count !== undefined && resource.resource_metadata.has_routes && (
                        <div className={`flex items-center gap-2 ${resource.resource_metadata.associated_subnets_count > 0 ? 'text-green-700' : 'text-red-700'}`}>
                          <span className="font-semibold">{resource.resource_metadata.associated_subnets_count > 0 ? '✓' : '✗'}</span>
                          <span>
                            {resource.resource_metadata.associated_subnets_count > 0
                              ? `Associated with ${resource.resource_metadata.associated_subnets_count} subnet(s)`
                              : 'Route tables NOT associated with any subnet'}
                          </span>
                        </div>
                      )}

                      {/* Internet Gateway check */}
                      {resource.resource_metadata?.vpc_has_igw !== undefined && (
                        <div className={`flex items-center gap-2 ${resource.resource_metadata.vpc_has_igw ? 'text-green-700' : 'text-red-700'}`}>
                          <span className="font-semibold">{resource.resource_metadata.vpc_has_igw ? '✓' : '✗'}</span>
                          <span>
                            {resource.resource_metadata.vpc_has_igw
                              ? 'VPC has Internet Gateway'
                              : 'VPC has NO Internet Gateway (cannot route to internet)'}
                          </span>
                        </div>
                      )}

                      {/* Age info */}
                      {resource.resource_metadata?.age_days !== undefined && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏱</span>
                          <span>NAT Gateway age: {resource.resource_metadata.age_days} days</span>
                        </div>
                      )}

                      {/* Confidence level with critical support */}
                      {resource.resource_metadata?.confidence && (
                        <div className={`flex items-center gap-2 ${
                          resource.resource_metadata.confidence === 'critical' ? 'text-red-900 font-bold' :
                          resource.resource_metadata.confidence === 'high' ? 'text-green-700' :
                          resource.resource_metadata.confidence === 'medium' ? 'text-yellow-700' :
                          'text-gray-700'
                        }`}>
                          <span className="font-semibold">
                            {resource.resource_metadata.confidence === 'critical' ? '🚨' :
                             resource.resource_metadata.confidence === 'high' ? '✓' :
                             resource.resource_metadata.confidence === 'medium' ? '◐' : '○'}
                          </span>
                          <span className="capitalize">
                            {resource.resource_metadata.confidence === 'critical' ? '🔥 CRITICAL' : resource.resource_metadata.confidence} confidence level
                          </span>
                        </div>
                      )}

                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">💡</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* EKS Cluster specific criteria */}
                  {resource.resource_type === 'eks_cluster' && (
                    <div className="space-y-2 text-sm">
                      {/* Kubernetes version badge */}
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-blue-200 rounded text-xs font-semibold">
                          K8s {resource.resource_metadata.version}
                        </span>
                        <span className="text-gray-600 text-xs">
                          {resource.resource_metadata.nodegroup_count} node group(s) | {resource.resource_metadata.total_nodes} node(s)
                          {resource.resource_metadata.fargate_profile_count > 0 && ` | ${resource.resource_metadata.fargate_profile_count} Fargate profile(s)`}
                        </span>
                      </div>

                      {/* Orphan type specific messages */}
                      {resource.resource_metadata?.orphan_type === 'no_worker_nodes' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🚫</span>
                            <span className="font-semibold">No worker nodes and no Fargate profiles</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">💰</span>
                            <span>Paying ${resource.resource_metadata.control_plane_cost_monthly}/month for unused control plane</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'all_nodes_unhealthy' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">⚠️</span>
                            <span className="font-semibold">All {resource.resource_metadata.total_nodes} nodes are unhealthy/degraded</span>
                          </div>
                          <div className="flex items-center gap-2 text-orange-600">
                            <span className="font-semibold">❌</span>
                            <span>Cluster unable to run workloads</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'low_utilization' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">💤</span>
                            <span className="font-semibold">All nodes have very low CPU utilization</span>
                          </div>
                          <div className="flex items-center gap-2 text-gray-600">
                            <span className="font-semibold">📊</span>
                            <span>Over-provisioned or abandoned cluster</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'fargate_no_profiles' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🔧</span>
                            <span className="font-semibold">Fargate-configured but no profiles created</span>
                          </div>
                          <div className="flex items-center gap-2 text-orange-600">
                            <span className="font-semibold">⚠️</span>
                            <span>Cannot deploy pods without Fargate profiles or node groups</span>
                          </div>
                        </>
                      )}

                      {resource.resource_metadata?.orphan_type === 'outdated_version' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">📅</span>
                            <span className="font-semibold">Outdated Kubernetes version (security risk)</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-600">
                            <span className="font-semibold">⚠️</span>
                            <span>Likely abandoned cluster</span>
                          </div>
                        </>
                      )}

                      {/* Node details */}
                      {resource.resource_metadata?.node_details && resource.resource_metadata.node_details.length > 0 && (
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1">
                          <div className="font-semibold text-gray-700">Node Groups:</div>
                          {resource.resource_metadata.node_details.map((node: any, idx: number) => (
                            <div key={idx} className="flex gap-2">
                              <span className="font-semibold">{node.name}:</span>
                              <span>{node.instance_type} × {node.desired_size} nodes</span>
                              <span className={node.status === 'ACTIVE' ? 'text-green-700' : 'text-red-700'}>
                                ({node.status})
                              </span>
                              {node.health_issues > 0 && (
                                <span className="text-red-700">⚠️ {node.health_issues} issue(s)</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Cost breakdown */}
                      {resource.resource_metadata.control_plane_cost_monthly !== undefined && (
                        <div className="text-xs text-gray-600">
                          💰 Control Plane: ${resource.resource_metadata.control_plane_cost_monthly}/mo
                          {resource.resource_metadata.node_cost_monthly > 0 && (
                            <> + Worker Nodes: ${resource.resource_metadata.node_cost_monthly}/mo</>
                          )}
                        </div>
                      )}

                      {/* Age and cluster status */}
                      <div className="flex items-center gap-4 text-xs text-gray-600">
                        <span>Status: <span className={`font-semibold ${resource.resource_metadata.status === 'ACTIVE' ? 'text-green-700' : 'text-orange-700'}`}>{resource.resource_metadata.status}</span></span>
                        <span>Age: {resource.resource_metadata.age_days} days</span>
                      </div>

                      {/* Confidence level */}
                      {resource.resource_metadata?.confidence_level && (
                        <div className={`flex items-center gap-2 ${
                          resource.resource_metadata.confidence_level === 'critical' ? 'text-red-900 font-bold' :
                          resource.resource_metadata.confidence_level === 'high' ? 'text-green-700' :
                          resource.resource_metadata.confidence_level === 'medium' ? 'text-yellow-700' :
                          'text-gray-700'
                        }`}>
                          <span className="font-semibold">
                            {resource.resource_metadata.confidence_level === 'critical' ? '🚨' :
                             resource.resource_metadata.confidence_level === 'high' ? '✓' :
                             resource.resource_metadata.confidence_level === 'medium' ? '◐' : '○'}
                          </span>
                          <span className="capitalize">
                            {resource.resource_metadata.confidence_level === 'critical' ? '🔥 CRITICAL' : resource.resource_metadata.confidence_level} confidence level
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* EBS Snapshot specific criteria */}
                  {resource.resource_type === 'ebs_snapshot' && (
                    <div className="space-y-1 text-sm">
                      {/* Check orphan type */}
                      {resource.resource_metadata?.orphan_type === 'volume_deleted' && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">✗</span>
                          <span>Source volume no longer exists (deleted)</span>
                        </div>
                      )}
                      {resource.resource_metadata?.orphan_type === 'idle_volume_snapshot' && (
                        <>
                          {resource.resource_metadata?.source_volume_status === 'unattached' && (
                            <div className="flex items-center gap-2 text-orange-700">
                              <span className="font-semibold">⚠️</span>
                              <span>
                                Snapshot of <span className="font-semibold">unattached</span> volume{' '}
                                <code className="bg-orange-100 px-1 rounded text-xs">
                                  {resource.resource_metadata?.volume_id}
                                </code>
                              </span>
                            </div>
                          )}
                          {resource.resource_metadata?.source_volume_status === 'attached_idle' && (
                            <div className="flex items-center gap-2 text-orange-700">
                              <span className="font-semibold">⚠️</span>
                              <span>
                                Snapshot of <span className="font-semibold">idle</span> volume{' '}
                                <code className="bg-orange-100 px-1 rounded text-xs">
                                  {resource.resource_metadata?.volume_id}
                                </code>
                              </span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Source volume is orphaned/unused (snapshot likely unnecessary)</span>
                          </div>
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'redundant_snapshot' && (
                        <>
                          <div className="flex items-center gap-2 text-purple-700">
                            <span className="font-semibold">🔄</span>
                            <span>
                              Redundant snapshot (position{' '}
                              <span className="font-semibold">
                                #{resource.resource_metadata?.redundant_info?.position}
                              </span>{' '}
                              of {resource.resource_metadata?.redundant_info?.total_snapshots})
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>
                              Exceeds retention limit ({resource.resource_metadata?.redundant_info?.retention_limit} snapshots)
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-purple-700">
                            <span className="font-semibold">💾</span>
                            <span>
                              Volume{' '}
                              <code className="bg-purple-100 px-1 rounded text-xs">
                                {resource.resource_metadata?.volume_id}
                              </code>{' '}
                              has too many backups
                            </span>
                          </div>
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'unused_ami_snapshot' && (
                        <>
                          <div className="flex items-center gap-2 text-indigo-700">
                            <span className="font-semibold">📀</span>
                            <span>
                              Snapshot of unused AMI{' '}
                              <code className="bg-indigo-100 px-1 rounded text-xs">
                                {resource.resource_metadata?.ami_info?.ami_id}
                              </code>
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>AMI not used to launch instances in 180+ days</span>
                          </div>
                          <div className="flex items-center gap-2 text-indigo-700">
                            <span className="font-semibold">ℹ️</span>
                            <span className="text-xs">Snapshot can be deleted if AMI is no longer needed</span>
                          </div>
                        </>
                      )}
                      {resource.resource_metadata?.age_days !== undefined && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">📅</span>
                          <span>
                            Snapshot created {resource.resource_metadata.age_days} day{resource.resource_metadata.age_days !== 1 ? 's' : ''} ago
                            {resource.resource_metadata.age_days >= 180 && ' (very old)'}
                            {resource.resource_metadata.age_days >= 90 && resource.resource_metadata.age_days < 180 && ' (old)'}
                            {resource.resource_metadata.age_days < 90 && ' (recent)'}
                          </span>
                        </div>
                      )}
                      {resource.resource_metadata?.size_gb && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">💾</span>
                          <span>Size: {resource.resource_metadata.size_gb} GB</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                      {resource.resource_metadata?.confidence === 'high' && (
                        <div className="flex items-center gap-2 text-green-700 mt-1 bg-green-50 p-2 rounded">
                          <span className="font-semibold">💡</span>
                          <span className="text-xs">Safe to delete if not needed for recovery or compliance</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* S3 Bucket specific criteria */}
                  {resource.resource_type === 's3_bucket' && (
                    <div className="space-y-1 text-sm">
                      {/* Check orphan type */}
                      {resource.resource_metadata?.orphan_type === 'empty' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Bucket is empty (0 objects)</span>
                          </div>
                          {resource.resource_metadata.bucket_age_days !== undefined && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">📅</span>
                              <span>Bucket age: {resource.resource_metadata.bucket_age_days} days</span>
                            </div>
                          )}
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'old_objects' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">⚠️</span>
                            <span>All {resource.resource_metadata.object_count} objects are very old</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>
                              Newest object is {resource.resource_metadata.newest_object_days}+ days old (no recent activity)
                            </span>
                          </div>
                          {resource.resource_metadata.bucket_size_gb > 0 && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💾</span>
                              <span>Size: {resource.resource_metadata.bucket_size_gb} GB</span>
                            </div>
                          )}
                          {resource.resource_metadata.storage_classes && Object.keys(resource.resource_metadata.storage_classes).length > 0 && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🗃️</span>
                              <span>
                                Storage classes: {Object.entries(resource.resource_metadata.storage_classes).map(([cls, size]) => `${cls} (${size} GB)`).join(', ')}
                              </span>
                            </div>
                          )}
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'multipart_uploads' && (
                        <>
                          <div className="flex items-center gap-2 text-purple-700">
                            <span className="font-semibold">🔄</span>
                            <span>Incomplete multipart uploads detected</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Abandoned uploads still consuming storage (hidden costs)</span>
                          </div>
                          {resource.resource_metadata.bucket_size_gb > 0 && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💾</span>
                              <span>Total size (including multiparts): {resource.resource_metadata.bucket_size_gb} GB</span>
                            </div>
                          )}
                        </>
                      )}
                      {resource.resource_metadata?.orphan_type === 'no_lifecycle' && (
                        <>
                          <div className="flex items-center gap-2 text-indigo-700">
                            <span className="font-semibold">📋</span>
                            <span>No lifecycle policy configured</span>
                          </div>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">⚠️</span>
                            <span>
                              Old objects ({resource.resource_metadata.oldest_object_days}+ days) could be transitioned to cheaper storage
                            </span>
                          </div>
                          {resource.resource_metadata.bucket_size_gb > 0 && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💾</span>
                              <span>Size: {resource.resource_metadata.bucket_size_gb} GB ({resource.resource_metadata.object_count} objects)</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-green-700 mt-1 bg-green-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs">Consider archiving to S3 Glacier or Glacier Deep Archive to reduce costs by 70-90%</span>
                          </div>
                        </>
                      )}
                      {/* Don't show region here, it's already displayed at the top in "S3 BUCKET · region" */}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* Lambda Function specific criteria */}
                  {resource.resource_type === 'lambda_function' && (
                    <div className="space-y-1 text-sm">
                      {/* Unused provisioned concurrency (HIGHEST PRIORITY) */}
                      {resource.resource_metadata?.orphan_type === 'unused_provisioned_concurrency' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🚨</span>
                            <span className="font-bold">CRITICAL: Unused Provisioned Concurrency</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">💸</span>
                            <span>Paying 24/7 for pre-warmed capacity that's not being used</span>
                          </div>
                          {resource.resource_metadata.memory_size_mb && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🧠</span>
                              <span>Memory: {resource.resource_metadata.memory_size_mb} MB</span>
                            </div>
                          )}
                          {resource.resource_metadata.runtime && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Runtime: {resource.resource_metadata.runtime}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-red-600 mt-1 bg-red-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs font-semibold">Remove provisioned concurrency immediately to stop wasting $10-100/month</span>
                          </div>
                        </>
                      )}
                      {/* Never invoked */}
                      {resource.resource_metadata?.orphan_type === 'never_invoked' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">⚠️</span>
                            <span className="font-semibold">Never invoked since creation</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Function created {resource.resource_metadata.age_days} days ago but never executed</span>
                          </div>
                          {resource.resource_metadata.memory_size_mb && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🧠</span>
                              <span>Memory: {resource.resource_metadata.memory_size_mb} MB</span>
                            </div>
                          )}
                          {resource.resource_metadata.runtime && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Runtime: {resource.resource_metadata.runtime}</span>
                            </div>
                          )}
                        </>
                      )}
                      {/* Zero invocations */}
                      {resource.resource_metadata?.orphan_type === 'zero_invocations' && (
                        <>
                          <div className="flex items-center gap-2 text-yellow-700">
                            <span className="font-semibold">⏰</span>
                            <span className="font-semibold">Zero invocations recently</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Not invoked in last 90 days - likely abandoned</span>
                          </div>
                          {resource.resource_metadata.memory_size_mb && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🧠</span>
                              <span>Memory: {resource.resource_metadata.memory_size_mb} MB</span>
                            </div>
                          )}
                          {resource.resource_metadata.runtime && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Runtime: {resource.resource_metadata.runtime}</span>
                            </div>
                          )}
                        </>
                      )}
                      {/* All failures */}
                      {resource.resource_metadata?.orphan_type === 'all_failures' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">❌</span>
                            <span className="font-bold">100% Failure Rate - Dead Function</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">💥</span>
                            <span>All invocations are failing - function is broken</span>
                          </div>
                          {resource.resource_metadata.memory_size_mb && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🧠</span>
                              <span>Memory: {resource.resource_metadata.memory_size_mb} MB</span>
                            </div>
                          )}
                          {resource.resource_metadata.runtime && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Runtime: {resource.resource_metadata.runtime}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-red-600 mt-1 bg-red-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs">Still charged for failed invocations - fix or delete to stop waste</span>
                          </div>
                        </>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* DynamoDB Table specific criteria */}
                  {resource.resource_type === 'dynamodb_table' && (
                    <div className="space-y-1 text-sm">
                      {/* Over-provisioned capacity (HIGHEST PRIORITY) */}
                      {resource.resource_metadata?.orphan_type === 'over_provisioned' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🚨</span>
                            <span className="font-bold">CRITICAL: Over-Provisioned Capacity</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">💸</span>
                            <span>Paying 24/7 for capacity barely used - major waste!</span>
                          </div>
                          {resource.resource_metadata.billing_mode && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💳</span>
                              <span>Billing: {resource.resource_metadata.billing_mode}</span>
                            </div>
                          )}
                          {(resource.resource_metadata.provisioned_read_capacity || resource.resource_metadata.provisioned_write_capacity) && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">📊</span>
                              <span>Provisioned: {resource.resource_metadata.provisioned_read_capacity} RCU / {resource.resource_metadata.provisioned_write_capacity} WCU</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-red-600 mt-1 bg-red-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs font-semibold">Switch to On-Demand billing or reduce provisioned capacity immediately</span>
                          </div>
                        </>
                      )}
                      {/* Unused GSI */}
                      {resource.resource_metadata?.orphan_type === 'unused_gsi' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">💰</span>
                            <span className="font-bold">Unused Global Secondary Index</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>GSI never queried - doubles your table cost for no benefit</span>
                          </div>
                          {resource.resource_metadata.billing_mode && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💳</span>
                              <span>Billing: {resource.resource_metadata.billing_mode}</span>
                            </div>
                          )}
                          {resource.resource_metadata.global_secondary_indexes_count && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🔢</span>
                              <span>Total GSIs: {resource.resource_metadata.global_secondary_indexes_count}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-orange-600 mt-1 bg-orange-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs">Delete unused GSI or verify if it's actually needed</span>
                          </div>
                        </>
                      )}
                      {/* Never used (Provisioned) */}
                      {resource.resource_metadata?.orphan_type === 'never_used_provisioned' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">⚠️</span>
                            <span className="font-semibold">Never Used - Provisioned Mode</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>Table created {resource.resource_metadata.age_days} days ago with 0 reads/writes - wasting provisioned capacity</span>
                          </div>
                          {resource.resource_metadata.billing_mode && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💳</span>
                              <span>Billing: {resource.resource_metadata.billing_mode}</span>
                            </div>
                          )}
                          {resource.resource_metadata.item_count !== undefined && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">📦</span>
                              <span>Items: {resource.resource_metadata.item_count}</span>
                            </div>
                          )}
                        </>
                      )}
                      {/* Never used (On-Demand) */}
                      {resource.resource_metadata?.orphan_type === 'never_used_ondemand' && (
                        <>
                          <div className="flex items-center gap-2 text-yellow-700">
                            <span className="font-semibold">📦</span>
                            <span className="font-semibold">On-Demand Table - No Usage</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>No reads/writes in last 60 days - likely orphaned</span>
                          </div>
                          {resource.resource_metadata.billing_mode && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💳</span>
                              <span>Billing: {resource.resource_metadata.billing_mode}</span>
                            </div>
                          )}
                          {resource.resource_metadata.table_size_gb && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💾</span>
                              <span>Size: {resource.resource_metadata.table_size_gb} GB (storage cost only)</span>
                            </div>
                          )}
                        </>
                      )}
                      {/* Empty table */}
                      {resource.resource_metadata?.orphan_type === 'empty_table' && (
                        <>
                          <div className="flex items-center gap-2 text-gray-700">
                            <span className="font-semibold">📭</span>
                            <span className="font-semibold">Empty Table</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>0 items since creation ({resource.resource_metadata.age_days} days ago)</span>
                          </div>
                          {resource.resource_metadata.billing_mode && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">💳</span>
                              <span>Billing: {resource.resource_metadata.billing_mode}</span>
                            </div>
                          )}
                        </>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* ElastiCache Cluster specific criteria */}
                  {resource.resource_type === 'elasticache_cluster' && (
                    <div className="space-y-1 text-sm">
                      {/* Zero cache hits (HIGHEST PRIORITY) */}
                      {resource.resource_metadata?.orphan_type === 'zero_cache_hits' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🚨</span>
                            <span className="font-bold">CRITICAL: Zero Cache Hits</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">✗</span>
                            <span>No cache activity for {resource.resource_metadata.age_days} days - cluster completely unused</span>
                          </div>
                          {resource.resource_metadata.engine && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Engine: {resource.resource_metadata.engine} {resource.resource_metadata.engine_version}</span>
                            </div>
                          )}
                          {resource.resource_metadata.node_type && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🖥️</span>
                              <span>{resource.resource_metadata.num_nodes}x {resource.resource_metadata.node_type}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-red-600 mt-1 bg-red-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs font-semibold">Delete this cluster immediately - zero activity detected</span>
                          </div>
                        </>
                      )}
                      {/* Low hit rate */}
                      {resource.resource_metadata?.orphan_type === 'low_hit_rate' && (
                        <>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">⚠️</span>
                            <span className="font-bold">{resource.resource_metadata.hit_rate < 10 ? 'CRITICAL: Very Low' : 'WARNING: Low'} Hit Rate</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">📉</span>
                            <span>Hit rate: {resource.resource_metadata.hit_rate}% (misses outnumber hits)</span>
                          </div>
                          <div className="flex items-center gap-2 text-gray-700">
                            <span className="font-semibold">📊</span>
                            <span>Hits: {resource.resource_metadata.cache_hits_7d?.toLocaleString() || 0} | Misses: {resource.resource_metadata.cache_misses_7d?.toLocaleString() || 0}</span>
                          </div>
                          {resource.resource_metadata.engine && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Engine: {resource.resource_metadata.engine} {resource.resource_metadata.engine_version}</span>
                            </div>
                          )}
                          {resource.resource_metadata.node_type && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🖥️</span>
                              <span>{resource.resource_metadata.num_nodes}x {resource.resource_metadata.node_type}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-orange-600 mt-1 bg-orange-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs font-semibold">Review caching strategy - data rarely reused ({resource.resource_metadata.hit_rate < 10 ? 'consider deleting' : 'optimize TTL/keys'})</span>
                          </div>
                        </>
                      )}
                      {/* No connections */}
                      {resource.resource_metadata?.orphan_type === 'no_connections' && (
                        <>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🚨</span>
                            <span className="font-bold">CRITICAL: No Connections</span>
                          </div>
                          <div className="flex items-center gap-2 text-red-700">
                            <span className="font-semibold">🔌</span>
                            <span>Zero active connections for {resource.resource_metadata.age_days} days - nobody connects</span>
                          </div>
                          {resource.resource_metadata.engine && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Engine: {resource.resource_metadata.engine} {resource.resource_metadata.engine_version}</span>
                            </div>
                          )}
                          {resource.resource_metadata.node_type && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🖥️</span>
                              <span>{resource.resource_metadata.num_nodes}x {resource.resource_metadata.node_type}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-red-600 mt-1 bg-red-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs font-semibold">Delete cluster - no applications using it</span>
                          </div>
                        </>
                      )}
                      {/* Over-provisioned memory */}
                      {resource.resource_metadata?.orphan_type === 'over_provisioned_memory' && (
                        <>
                          <div className="flex items-center gap-2 text-yellow-700">
                            <span className="font-semibold">💰</span>
                            <span className="font-bold">WARNING: Over-Provisioned Memory</span>
                          </div>
                          <div className="flex items-center gap-2 text-orange-700">
                            <span className="font-semibold">📏</span>
                            <span>Memory usage: {resource.resource_metadata.memory_usage_percent}% (very low utilization)</span>
                          </div>
                          <div className="flex items-center gap-2 text-gray-700">
                            <span className="font-semibold">✓</span>
                            <span>0 evictions detected - cluster is too large for workload</span>
                          </div>
                          {resource.resource_metadata.engine && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">⚙️</span>
                              <span>Engine: {resource.resource_metadata.engine} {resource.resource_metadata.engine_version}</span>
                            </div>
                          )}
                          {resource.resource_metadata.node_type && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🖥️</span>
                              <span>{resource.resource_metadata.num_nodes}x {resource.resource_metadata.node_type}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-yellow-600 mt-1 bg-yellow-50 p-2 rounded">
                            <span className="font-semibold">💡</span>
                            <span className="text-xs font-semibold">Downgrade to smaller node type to save costs</span>
                          </div>
                        </>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  {/* Azure Managed Disk specific criteria */}
                  {resource.resource_type === 'managed_disk_unattached' && (
                    <div className="space-y-2 text-sm">
                      {/* Disk SKU and Size */}
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          resource.resource_metadata?.sku_name?.includes('Premium') ? 'bg-purple-100 text-purple-700' :
                          resource.resource_metadata?.sku_name?.includes('StandardSSD') ? 'bg-blue-100 text-blue-700' :
                          resource.resource_metadata?.sku_name?.includes('UltraSSD') ? 'bg-red-100 text-red-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {resource.resource_metadata?.sku_name || 'Unknown SKU'}
                        </span>
                        <span className="text-gray-600">{resource.resource_metadata?.disk_size_gb || 0} GB</span>
                        {resource.resource_metadata?.sku_tier && (
                          <span className="text-xs text-gray-500">({resource.resource_metadata.sku_tier})</span>
                        )}
                      </div>

                      {/* Disk State */}
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">✗</span>
                        <span className="font-semibold">Status: {resource.resource_metadata?.disk_state || 'Unknown'}</span>
                      </div>

                      {/* Reserved state warning */}
                      {resource.resource_metadata?.disk_state === 'Reserved' && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⚠️</span>
                          <span>Disk in Reserved state - billing continues even when not attached</span>
                        </div>
                      )}

                      {/* Encryption status */}
                      {resource.resource_metadata?.encryption_type && (
                        <div className="flex items-center gap-2 text-blue-700">
                          <span className="font-semibold">🔐</span>
                          <span>Encryption: {resource.resource_metadata.encryption_type}</span>
                        </div>
                      )}

                      {/* Availability Zone */}
                      {resource.resource_metadata?.zones && resource.resource_metadata.zones.length > 0 && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">📍</span>
                          <span>Zone: {resource.resource_metadata.zones.join(', ')}</span>
                        </div>
                      )}

                      {/* Bursting enabled */}
                      {resource.resource_metadata?.bursting_enabled && (
                        <div className="flex items-center gap-2 text-purple-700">
                          <span className="font-semibold">⚡</span>
                          <span>Bursting enabled (+15% cost)</span>
                        </div>
                      )}

                      {/* Ultra SSD details */}
                      {resource.resource_metadata?.sku_name?.includes('UltraSSD') && (
                        <>
                          {resource.resource_metadata?.disk_iops && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">📊</span>
                              <span>IOPS: {resource.resource_metadata.disk_iops.toLocaleString()}</span>
                            </div>
                          )}
                          {resource.resource_metadata?.disk_mbps && (
                            <div className="flex items-center gap-2 text-gray-700">
                              <span className="font-semibold">🚀</span>
                              <span>Throughput: {resource.resource_metadata.disk_mbps} MB/s</span>
                            </div>
                          )}
                          {resource.resource_metadata?.warning && (
                            <div className="flex items-center gap-2 text-red-600 mt-1 bg-red-50 p-2 rounded">
                              <span className="font-semibold">💡</span>
                              <span className="text-xs">{resource.resource_metadata.warning}</span>
                            </div>
                          )}
                        </>
                      )}

                      {/* Orphan reason */}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata?.orphan_reason || 'Unattached Azure Managed Disk'}</span>
                      </div>

                      {/* Age information */}
                      {resource.resource_metadata?.age_days !== undefined && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏱</span>
                          <span>Unattached for {resource.resource_metadata.age_days} days</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Azure Public IP specific criteria */}
                  {resource.resource_type === 'public_ip_unassociated' && (
                    <div className="space-y-2 text-sm">
                      {/* SKU and Allocation Method */}
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          resource.resource_metadata?.sku_name === 'Standard' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {resource.resource_metadata?.sku_name || 'Basic'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          resource.resource_metadata?.allocation_method === 'Static' ? 'bg-green-100 text-green-700' :
                          'bg-orange-100 text-orange-700'
                        }`}>
                          {resource.resource_metadata?.allocation_method || 'Unknown'}
                        </span>
                      </div>

                      {/* IP Address */}
                      {resource.resource_metadata?.ip_address && resource.resource_metadata.ip_address !== 'Not assigned' && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">🌐</span>
                          <span className="font-mono">{resource.resource_metadata.ip_address}</span>
                        </div>
                      )}

                      {/* Status */}
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">✗</span>
                        <span className="font-semibold">Status: Unassociated</span>
                      </div>

                      {/* DNS Settings */}
                      {resource.resource_metadata?.dns_label && (
                        <div className="flex items-center gap-2 text-purple-700">
                          <span className="font-semibold">🔗</span>
                          <span>DNS: {resource.resource_metadata.dns_label}</span>
                          {resource.resource_metadata?.fqdn && (
                            <span className="text-xs text-gray-500">({resource.resource_metadata.fqdn})</span>
                          )}
                        </div>
                      )}

                      {/* Availability Zones */}
                      {resource.resource_metadata?.zones && resource.resource_metadata.zones.length > 0 && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">📍</span>
                          <span>Zone{resource.resource_metadata.zones.length > 1 ? 's' : ''}: {resource.resource_metadata.zones.join(', ')}</span>
                          {resource.resource_metadata.zones.length >= 3 && (
                            <span className="text-xs text-blue-600">(Zone-redundant +22%)</span>
                          )}
                        </div>
                      )}

                      {/* Dynamic IP Warning */}
                      {resource.resource_metadata?.allocation_method === 'Dynamic' && resource.resource_metadata?.warning && (
                        <div className="flex items-center gap-2 text-orange-600 mt-1 bg-orange-50 p-2 rounded">
                          <span className="font-semibold">⚠️</span>
                          <span className="text-xs">{resource.resource_metadata.warning}</span>
                        </div>
                      )}

                      {/* Zone-redundant Warning */}
                      {resource.resource_metadata?.warning_zone && (
                        <div className="flex items-center gap-2 text-blue-600 mt-1 bg-blue-50 p-2 rounded">
                          <span className="font-semibold">💡</span>
                          <span className="text-xs">{resource.resource_metadata.warning_zone}</span>
                        </div>
                      )}

                      {/* Orphan reason */}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata?.orphan_reason || 'Unassociated Azure Public IP'}</span>
                      </div>

                      {/* Age information */}
                      {resource.resource_metadata?.age_days !== undefined && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏱</span>
                          <span>Unassociated for {resource.resource_metadata.age_days} days</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Azure VM Deallocated specific criteria */}
                  {resource.resource_type === 'virtual_machine_deallocated' && (
                    <div className="space-y-1 text-sm">
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">✗</span>
                        <span>Virtual machine deallocated (stopped)</span>
                      </div>
                      {resource.resource_metadata?.stopped_days !== undefined && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏱</span>
                          <span>Stopped for {resource.resource_metadata.stopped_days} days</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">💡</span>
                        <span className="italic">{resource.resource_metadata?.orphan_reason || 'Deallocated Azure VM'}</span>
                      </div>
                    </div>
                  )}

                  {/* Azure Snapshot specific criteria */}
                  {resource.resource_type === 'disk_snapshot_orphaned' && (
                    <div className="space-y-1 text-sm">
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">✗</span>
                        <span>Orphaned snapshot (source disk deleted or unused)</span>
                      </div>
                      {resource.resource_metadata?.age_days !== undefined && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">📅</span>
                          <span>Snapshot age: {resource.resource_metadata.age_days} days</span>
                        </div>
                      )}
                      {resource.resource_metadata?.size_gb && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">💾</span>
                          <span>Size: {resource.resource_metadata.size_gb} GB</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata?.orphan_reason || 'Orphaned Azure Disk Snapshot'}</span>
                      </div>
                    </div>
                  )}

                  {/* Azure Phase 1: Managed Disk on Stopped VM */}
                  {resource.resource_type === 'managed_disk_on_stopped_vm' && (
                    <div className="space-y-2 text-sm">
                      {/* Disk SKU and Size */}
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          resource.resource_metadata?.sku_name?.includes('Premium') ? 'bg-purple-100 text-purple-700' :
                          resource.resource_metadata?.sku_name?.includes('StandardSSD') ? 'bg-blue-100 text-blue-700' :
                          resource.resource_metadata?.sku_name?.includes('UltraSSD') ? 'bg-red-100 text-red-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {resource.resource_metadata?.sku_name || 'Unknown SKU'}
                        </span>
                        <span className="text-gray-600">{resource.resource_metadata?.disk_size_gb || 0} GB</span>
                      </div>

                      {/* Attached VM Info */}
                      <div className="flex items-center gap-2 text-orange-700">
                        <span className="font-semibold">💻</span>
                        <span className="font-semibold">VM: {resource.resource_metadata?.vm_name || 'Unknown'}</span>
                      </div>

                      {/* VM Power State */}
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">⏸️</span>
                        <span className="font-semibold">VM Status: Deallocated (Stopped)</span>
                      </div>

                      {/* Stopped Duration */}
                      {resource.resource_metadata?.stopped_days !== undefined && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏱</span>
                          <span>VM stopped for {resource.resource_metadata.stopped_days} days</span>
                        </div>
                      )}

                      {/* Disk Type (OS vs Data) */}
                      {resource.resource_metadata?.disk_type && (
                        <div className="flex items-center gap-2 text-blue-700">
                          <span className="font-semibold">📀</span>
                          <span>{resource.resource_metadata.disk_type === 'os' ? 'OS Disk' : 'Data Disk'}</span>
                        </div>
                      )}

                      {/* Orphan reason */}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata?.orphan_reason || 'Disk attached to stopped VM incurring charges'}</span>
                      </div>

                      {/* Warning message */}
                      <div className="flex items-center gap-2 text-amber-600 mt-1 bg-amber-50 p-2 rounded">
                        <span className="font-semibold">💡</span>
                        <span className="text-xs">Consider deleting unused VMs or detaching/deleting unused disks</span>
                      </div>
                    </div>
                  )}

                  {/* Azure Phase 1: Public IP on Stopped Resource */}
                  {resource.resource_type === 'public_ip_on_stopped_resource' && (
                    <div className="space-y-2 text-sm">
                      {/* SKU and Allocation Method */}
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          resource.resource_metadata?.sku_name === 'Standard' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {resource.resource_metadata?.sku_name || 'Basic'}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                          resource.resource_metadata?.allocation_method === 'Static' ? 'bg-green-100 text-green-700' :
                          'bg-orange-100 text-orange-700'
                        }`}>
                          {resource.resource_metadata?.allocation_method || 'Unknown'}
                        </span>
                      </div>

                      {/* IP Address */}
                      {resource.resource_metadata?.ip_address && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">🌐</span>
                          <span className="font-mono">{resource.resource_metadata.ip_address}</span>
                        </div>
                      )}

                      {/* Attached Resource Type */}
                      {resource.resource_metadata?.attached_resource_type && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">🔗</span>
                          <span>Attached to: {resource.resource_metadata.attached_resource_type}</span>
                        </div>
                      )}

                      {/* Attached Resource Name */}
                      {resource.resource_metadata?.attached_resource_name && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">📌</span>
                          <span>{resource.resource_metadata.attached_resource_name}</span>
                        </div>
                      )}

                      {/* Resource Status */}
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">⏸️</span>
                        <span className="font-semibold">Resource Status: Stopped/Inactive</span>
                      </div>

                      {/* Stopped Duration */}
                      {resource.resource_metadata?.stopped_days !== undefined && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏱</span>
                          <span>Resource stopped for {resource.resource_metadata.stopped_days} days</span>
                        </div>
                      )}

                      {/* Orphan reason */}
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata?.orphan_reason || 'Public IP on stopped resource incurring charges'}</span>
                      </div>

                      {/* Warning message */}
                      <div className="flex items-center gap-2 text-amber-600 mt-1 bg-amber-50 p-2 rounded">
                        <span className="font-semibold">💡</span>
                        <span className="text-xs">Consider releasing unused public IPs or starting the associated resource</span>
                      </div>
                    </div>
                  )}

                  {/* Azure Storage Account specific criteria */}
                  {(resource.resource_type === 'storage_account_empty' ||
                    resource.resource_type === 'storage_account_never_used' ||
                    resource.resource_type === 'storage_account_no_transactions') && (
                    <div className="space-y-2 text-sm">
                      {/* Storage Account SKU and Replication */}
                      {resource.resource_metadata?.sku && (
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            resource.resource_metadata.sku.includes('Premium') ? 'bg-purple-100 text-purple-700' :
                            resource.resource_metadata.sku.includes('Standard') ? 'bg-blue-100 text-blue-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {resource.resource_metadata.sku}
                          </span>
                          {resource.resource_metadata?.replication && (
                            <span className="text-xs text-gray-600">
                              {resource.resource_metadata.replication}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Status */}
                      {resource.resource_metadata?.status && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">✗</span>
                          <span className="font-semibold">Status: {resource.resource_metadata.status}</span>
                        </div>
                      )}

                      {/* Container and blob info */}
                      {resource.resource_metadata?.container_count !== undefined && (
                        <div className="flex items-center gap-2 text-gray-700">
                          <span className="font-semibold">📦</span>
                          <span>
                            {resource.resource_metadata.container_count} container(s),
                            {' '}{resource.resource_metadata.blob_count || 0} blob(s)
                            {resource.resource_metadata.total_size_gb !== undefined &&
                              ` (${resource.resource_metadata.total_size_gb.toFixed(2)} GB)`
                            }
                          </span>
                        </div>
                      )}

                      {/* Last accessed */}
                      {resource.resource_metadata?.last_accessed && (
                        <div className="flex items-center gap-2 text-orange-700">
                          <span className="font-semibold">⏰</span>
                          <span>Last accessed: {resource.resource_metadata.last_accessed}</span>
                        </div>
                      )}

                      {/* Empty/Never used days */}
                      {(resource.resource_metadata?.empty_days || resource.resource_metadata?.never_used_days) && (
                        <div className="flex items-center gap-2 text-red-700">
                          <span className="font-semibold">🔥</span>
                          <span>
                            {resource.resource_type === 'storage_account_never_used'
                              ? `Never used for ${resource.resource_metadata.never_used_days || resource.resource_metadata.age_days} days`
                              : `Empty for ${resource.resource_metadata.empty_days || resource.resource_metadata.age_days} days`
                            }
                          </span>
                        </div>
                      )}

                      {/* Why orphaned message */}
                      {resource.resource_metadata?.why_orphaned && (
                        <div className="flex items-start gap-2 text-gray-600 mt-1 bg-gray-50 p-2 rounded">
                          <span className="font-semibold">ℹ️</span>
                          <span className="italic">{resource.resource_metadata.why_orphaned}</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Generic criteria for other resource types */}
                  {!['ebs_volume', 'elastic_ip', 'rds_instance', 'ec2_instance', 'load_balancer', 'nat_gateway', 'ebs_snapshot', 'eks_cluster', 's3_bucket', 'lambda_function', 'dynamodb_table', 'elasticache_cluster', 'managed_disk_unattached', 'public_ip_unassociated', 'virtual_machine_deallocated', 'disk_snapshot_orphaned', 'managed_disk_on_stopped_vm', 'public_ip_on_stopped_resource', 'storage_account_empty', 'storage_account_never_used', 'storage_account_no_transactions'].includes(resource.resource_type) && (
                    <div className="text-sm">
                      <div className="flex items-center gap-2 text-gray-700">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.why_orphaned || resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  <div className="mt-2 pt-2 border-t border-amber-300">
                    <p className="text-xs text-amber-800">
                      💡 <strong>What to do:</strong>{' '}
                      {resource.resource_metadata?.recommendation ||
                       resource.resource_metadata?.action_required ||
                       'Review this resource on your cloud console and delete it if no longer needed to stop wasting money.'}
                    </p>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 text-sm">
                <div className="flex items-center gap-1">
                  <span className="text-gray-500">Future waste:</span>
                  <span className="font-semibold text-orange-600" title="Estimated monthly cost if this resource stays orphaned">
                    ${resource.estimated_monthly_cost.toFixed(2)}/month
                  </span>
                </div>
                {cumulativeCost !== null && displayAge && (
                  <div className="flex items-center gap-1">
                    <span className="text-gray-500">·</span>
                    <span className="text-gray-500">Already wasted:</span>
                    <span className="font-semibold text-red-600" title={`Money already wasted since resource creation (${displayAge} ago)`}>
                      ${cumulativeCost.toFixed(2)}
                    </span>
                    <span className="text-xs text-gray-400">over {displayAge}</span>
                  </div>
                )}
                {ageDays === -1 && (
                  <div className="flex items-center gap-1">
                    <span className="text-gray-500">·</span>
                    <span className="text-xs text-gray-400 italic">
                      Age unknown (add "CreatedDate" tag for tracking)
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Metadata */}
            {expanded && resource.resource_metadata && (
              <div className="mt-4 rounded-lg bg-gray-50 p-4">
                <h4 className="text-sm font-semibold text-gray-700">Metadata</h4>
                <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
                  {Object.entries(resource.resource_metadata).map(([key, value]) => (
                    <div key={key}>
                      <dt className="font-medium text-gray-600">
                        {key.replace(/_/g, " ")}:
                      </dt>
                      <dd className="text-gray-900">
                        {typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <Eye className="h-5 w-5" />
          </button>
          {resource.status === "active" && (
            <>
              <button
                onClick={onIgnore}
                className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                title="Ignore this resource"
              >
                <EyeOff className="h-5 w-5" />
              </button>
              <button
                onClick={onMarkForDeletion}
                className="rounded-lg p-2 text-gray-400 hover:bg-orange-100 hover:text-orange-600"
                title="Mark for deletion"
              >
                <Trash2 className="h-5 w-5" />
              </button>
            </>
          )}
          <button
            onClick={onDelete}
            className="rounded-lg p-2 text-gray-400 hover:bg-red-100 hover:text-red-600"
            title="Delete record"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
