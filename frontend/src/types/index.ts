/**
 * TypeScript type definitions for CloudWaste
 */

// User types
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Cloud Account types
export interface CloudAccount {
  id: string;
  user_id: string;
  provider: "aws" | "azure" | "gcp";
  account_name: string;
  account_identifier: string;
  regions: string[] | null;
  resource_groups: string[] | null;
  description: string | null;
  is_active: boolean;
  last_scan_at: string | null;
  scheduled_scan_enabled: boolean;
  scheduled_scan_frequency: string;
  scheduled_scan_hour: number;
  scheduled_scan_day_of_week: number | null;
  scheduled_scan_day_of_month: number | null;
  created_at: string;
  updated_at: string;
}

export interface CloudAccountCreate {
  provider: "aws" | "azure";
  account_name: string;
  account_identifier: string;

  // AWS credentials
  aws_access_key_id?: string;
  aws_secret_access_key?: string;

  // Azure credentials
  azure_tenant_id?: string;
  azure_client_id?: string;
  azure_client_secret?: string;
  azure_subscription_id?: string;

  regions?: string[];
  resource_groups?: string[];
  description?: string;
}

// Scan types
export type ScanStatus = "pending" | "in_progress" | "completed" | "failed";
export type ScanType = "manual" | "scheduled";

export interface Scan {
  id: string;
  cloud_account_id: string;
  status: ScanStatus;
  scan_type: ScanType;
  total_resources_scanned: number;
  orphan_resources_found: number;
  estimated_monthly_waste: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScanCreate {
  cloud_account_id: string;
  scan_type?: ScanType;
}

export interface ScanWithResources extends Scan {
  orphan_resources: OrphanResource[];
}

export interface ScanSummary {
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
  total_orphan_resources: number;
  total_monthly_waste: number;
  last_scan_at: string | null;
}

// Orphan Resource types
export type ResourceStatus = "active" | "ignored" | "marked_for_deletion" | "deleted";

export type ResourceType =
  // AWS Resources
  | "ebs_volume"
  | "elastic_ip"
  | "ebs_snapshot"
  | "ec2_instance"
  | "load_balancer"
  | "rds_instance"
  | "nat_gateway"
  | "fsx_file_system"
  | "neptune_cluster"
  | "msk_cluster"
  | "eks_cluster"
  | "sagemaker_endpoint"
  | "redshift_cluster"
  | "elasticache_cluster"
  | "vpn_connection"
  | "transit_gateway_attachment"
  | "opensearch_domain"
  | "global_accelerator"
  | "kinesis_stream"
  | "vpc_endpoint"
  | "documentdb_cluster"
  | "s3_bucket"
  | "lambda_function"
  | "dynamodb_table"
  // Azure Resources
  | "managed_disk_unattached"
  | "public_ip_unassociated"
  | "disk_snapshot_orphaned"
  | "virtual_machine_deallocated"
  // Azure Phase 1 - Advanced waste scenarios
  | "managed_disk_on_stopped_vm"
  | "public_ip_on_stopped_resource"
  // Azure VM Phase A - Virtual Machine waste scenarios
  | "virtual_machine_stopped_not_deallocated"
  | "virtual_machine_never_started"
  | "virtual_machine_oversized_premium"
  | "virtual_machine_untagged_orphan"
  // Azure Storage Accounts
  | "storage_account_empty"
  | "storage_account_never_used"
  | "storage_account_no_transactions"
  // Azure Container Apps - Phase 1 (10 scenarios)
  | "container_app_stopped"
  | "container_app_zero_replicas"
  | "container_app_unnecessary_premium_tier"
  | "container_app_dev_zone_redundancy"
  | "container_app_no_ingress_configured"
  | "container_app_empty_environment"
  | "container_app_unused_revision"
  | "container_app_overprovisioned_cpu_memory"
  | "container_app_custom_domain_unused"
  | "container_app_secrets_unused"
  // Azure Container Apps - Phase 2 (6 scenarios with Azure Monitor)
  | "container_app_low_cpu_utilization"
  | "container_app_low_memory_utilization"
  | "container_app_zero_http_requests"
  | "container_app_high_replica_low_traffic"
  | "container_app_autoscaling_not_triggering"
  | "container_app_cold_start_issues"
  // Azure Virtual Desktop - Phase 1 (12 scenarios)
  | "avd_host_pool_empty"
  | "avd_session_host_stopped"
  | "avd_session_host_never_used"
  | "avd_host_pool_no_autoscale"
  | "avd_host_pool_over_provisioned"
  | "avd_application_group_empty"
  | "avd_workspace_empty"
  | "avd_premium_disk_in_dev"
  | "avd_unnecessary_availability_zones"
  | "avd_personal_desktop_never_used"
  | "avd_fslogix_oversized"
  | "avd_session_host_old_vm_generation"
  // Azure Virtual Desktop - Phase 2 (6 scenarios with Azure Monitor)
  | "avd_low_cpu_utilization"
  | "avd_low_memory_utilization"
  | "avd_zero_user_sessions"
  | "avd_high_host_count_low_users"
  | "avd_disconnected_sessions_waste"
  | "avd_peak_hours_mismatch"
  // Azure HDInsight Spark Cluster - Phase 1 (10 scenarios)
  | "hdinsight_spark_cluster_stopped"
  | "hdinsight_spark_cluster_never_used"
  | "hdinsight_spark_premium_storage_dev"
  | "hdinsight_spark_no_autoscale"
  | "hdinsight_spark_outdated_version"
  | "hdinsight_spark_external_metastore_unused"
  | "hdinsight_spark_empty_cluster"
  | "hdinsight_spark_oversized_head_nodes"
  | "hdinsight_spark_unnecessary_edge_node"
  | "hdinsight_spark_undersized_disks"
  // Azure HDInsight Spark Cluster - Phase 2 (8 scenarios with Azure Monitor + Ambari)
  | "hdinsight_spark_low_cpu_utilization"
  | "hdinsight_spark_zero_jobs_metrics"
  | "hdinsight_spark_idle_business_hours"
  | "hdinsight_spark_high_yarn_memory_waste"
  | "hdinsight_spark_excessive_shuffle_data"
  | "hdinsight_spark_autoscale_not_working"
  | "hdinsight_spark_low_memory_utilization"
  | "hdinsight_spark_high_job_failure_rate";

export type ConfidenceLevel = "critical" | "high" | "medium" | "low";

export interface OrphanResource {
  id: string;
  scan_id: string;
  cloud_account_id: string;
  resource_type: ResourceType;
  resource_id: string;
  resource_name: string | null;
  region: string;
  estimated_monthly_cost: number;
  resource_metadata: Record<string, any> | null;
  status: ResourceStatus;
  created_at: string;
  updated_at: string;
  confidence_level?: ConfidenceLevel; // Extracted from resource_metadata for convenience
}

export interface OrphanResourceUpdate {
  status?: ResourceStatus;
  resource_name?: string;
}

export interface OrphanResourceStats {
  total_resources: number;
  by_type: Record<string, number>;
  by_region: Record<string, number>;
  by_status: Record<string, number>;
  total_monthly_cost: number;
  total_annual_cost: number;
}

export interface ResourceCostBreakdown {
  resource_type: string;
  count: number;
  total_monthly_cost: number;
  percentage: number;
}

// API Error types
export interface APIError {
  detail: string;
}

// Filter types
export interface ResourceFilters {
  cloud_account_id?: string;
  status?: ResourceStatus;
  resource_type?: ResourceType;
  skip?: number;
  limit?: number;
}

export interface ScanFilters {
  cloud_account_id?: string;
  skip?: number;
  limit?: number;
}

// Chat types
export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  message_metadata?: Record<string, any>;
  created_at: string;
}

export interface ChatConversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
}

export interface ChatConversationListItem {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatConversationCreate {
  title: string;
}

export interface ChatMessageCreate {
  content: string;
}

// Admin types
export interface UserAdminUpdate {
  is_active?: boolean;
  is_superuser?: boolean;
}

export interface AdminStats {
  total_users: number;
  active_users: number;
  inactive_users: number;
  superusers: number;
}
