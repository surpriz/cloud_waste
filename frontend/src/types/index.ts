/**
 * TypeScript type definitions for CutCosts
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
  provider: "aws" | "azure" | "gcp" | "microsoft365";
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
  provider: "aws" | "azure" | "gcp" | "microsoft365";
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

  // GCP credentials
  gcp_project_id?: string;
  gcp_service_account_json?: string;

  // Microsoft 365 credentials
  microsoft365_tenant_id?: string;
  microsoft365_client_id?: string;
  microsoft365_client_secret?: string;

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
  celery_task_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScanProgress {
  state: "PENDING" | "PROGRESS" | "SUCCESS" | "FAILURE";
  current: number;
  total: number;
  percent: number;
  current_step: string;
  region: string;
  resources_found: number;
  elapsed_seconds: number;
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
  | "hdinsight_spark_high_job_failure_rate"
  // Azure Machine Learning Compute Instance - Phase 1 (10 scenarios)
  | "ml_compute_instance_no_auto_shutdown"
  | "ml_compute_instance_gpu_for_cpu_workload"
  | "ml_compute_instance_stopped_30_days"
  | "ml_compute_instance_over_provisioned"
  | "ml_compute_instance_never_accessed"
  | "ml_compute_instance_multiple_per_user"
  | "ml_compute_instance_premium_ssd_unnecessary"
  | "ml_compute_instance_no_idle_shutdown"
  | "ml_compute_instance_dev_high_performance_sku"
  | "ml_compute_instance_old_sdk_deprecated_image"
  // Azure Machine Learning Compute Instance - Phase 2 (8 scenarios with Azure Monitor)
  | "ml_compute_instance_low_cpu_utilization"
  | "ml_compute_instance_low_gpu_utilization"
  | "ml_compute_instance_idle_business_hours"
  | "ml_compute_instance_no_jupyter_activity"
  | "ml_compute_instance_no_training_jobs"
  | "ml_compute_instance_low_memory_utilization"
  | "ml_compute_instance_network_idle"
  | "ml_compute_instance_disk_io_near_zero"
  // Azure App Service (Web Apps) - Phase 1 (10 scenarios)
  | "app_service_plan_empty"
  | "app_service_premium_in_dev"
  | "app_service_no_auto_scale"
  | "app_service_always_on_low_traffic"
  | "app_service_unused_deployment_slots"
  | "app_service_over_provisioned_plan"
  | "app_service_stopped_apps_paid_plan"
  | "app_service_multiple_plans_consolidation"
  | "app_service_vnet_integration_unused"
  | "app_service_old_runtime_version"
  // Azure App Service (Web Apps) - Phase 2 (8 scenarios with Azure Monitor)
  | "app_service_low_cpu_utilization"
  | "app_service_low_memory_utilization"
  | "app_service_low_request_count"
  | "app_service_no_traffic_business_hours"
  | "app_service_high_http_error_rate"
  | "app_service_slow_response_time"
  | "app_service_auto_scale_never_triggers"
  | "app_service_cold_start_excessive"
  // Azure Networking (ExpressRoute, VPN, NICs) - 8 scenarios
  | "expressroute_circuit_not_provisioned"
  | "expressroute_circuit_no_connection"
  | "expressroute_gateway_orphaned"
  | "expressroute_circuit_underutilized"
  | "vpn_gateway_disconnected"
  | "vpn_gateway_basic_sku_deprecated"
  | "vpn_gateway_no_connections"
  | "network_interface_orphaned"
  // GCP Resources (10 for MVP Phase 1)
  | "gce_instance_stopped"
  | "gce_instance_idle"
  | "gke_cluster_idle"
  | "persistent_disk_unattached"
  | "gcs_bucket_empty"
  | "disk_snapshot_old"
  | "static_ip_unattached"
  | "nat_gateway_unused"
  | "cloud_sql_stopped"
  | "cloud_sql_idle"
  // Azure - Cost Intelligence (Inventory mode)
  | "azure_vm"
  | "azure_managed_disk"
  | "azure_public_ip"
  | "azure_load_balancer"
  | "azure_app_gateway"
  | "azure_storage_account"
  | "azure_expressroute_circuit"
  | "azure_disk_snapshot"
  | "azure_nat_gateway"
  | "azure_sql_database"
  | "azure_aks_cluster"
  | "azure_function_app"
  | "azure_cosmos_db"
  | "azure_container_app"
  | "azure_virtual_desktop"
  | "azure_hdinsight_cluster"
  | "azure_ml_compute"
  | "azure_app_service"
  | "azure_redis_cache"
  | "azure_event_hub"
  | "azure_netapp_files"
  | "azure_cognitive_search"
  | "azure_api_management"
  | "azure_cdn"
  | "azure_container_instance"
  | "azure_logic_app"
  | "azure_log_analytics"
  | "azure_backup_vault"
  | "azure_data_factory_pipeline"
  | "azure_synapse_serverless_sql"
  | "azure_storage_sftp"
  | "azure_ad_domain_services"
  | "azure_service_bus_premium"
  | "azure_iot_hub"
  | "azure_stream_analytics"
  | "azure_document_intelligence"
  | "azure_computer_vision"
  | "azure_face_api"
  | "azure_text_analytics"
  | "azure_speech_services"
  | "azure_bot_service"
  | "azure_application_insights"
  | "azure_managed_devops_pools"
  | "azure_private_endpoint"
  | "azure_cosmos_db_gremlin"
  | "azure_hdinsight_kafka"
  | "azure_ml_endpoint"
  | "azure_synapse_sql_pool"
  | "azure_vpn_gateway";

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

// Pricing types
export interface PricingCacheItem {
  provider: string;
  service: string;
  region: string;
  price_per_unit: number;
  unit: string;
  currency: string;
  source: string;
  last_updated: string;
  expires_at: string;
  is_expired: boolean;
}

export interface PricingStats {
  total_cached_prices: number;
  expired_prices: number;
  api_sourced_prices: number;
  fallback_sourced_prices: number;
  last_refresh_at: string | null;
  cache_hit_rate: number;
  api_success_rate: number;
}

export interface PricingRefreshResponse {
  status: string;
  task_id: string | null;
  message: string;
  updated_count: number | null;
  failed_count: number | null;
}

// ML Data Collection types
export interface MLDataStats {
  total_ml_records: number;
  total_user_actions: number;
  total_cost_trends: number;
  records_last_7_days: number;
  records_last_30_days: number;
  last_collection_date: string | null;
}

export interface MLExportResponse {
  success: boolean;
  message: string;
  files: Record<string, string>;
  total_records_exported: number;
}

// AWS SES Email Monitoring types
export interface SESMetrics {
  // Send Statistics
  emails_sent_24h: number;
  emails_sent_7d: number;
  emails_sent_30d: number;

  // Deliverability Rates (percentages)
  delivery_rate: number;
  bounce_rate: number;
  complaint_rate: number;

  // Hard vs Soft Bounces
  hard_bounce_rate: number;
  soft_bounce_rate: number;

  // Send Quotas
  max_send_rate: number;
  daily_quota: number;
  daily_sent: number;
  quota_usage_percentage: number;

  // Account Reputation & Status
  reputation_status: "healthy" | "under_review" | "probation";
  sending_enabled: boolean;
  suppression_list_size: number;

  // Alerts
  has_critical_alerts: boolean;
  alerts: string[];

  // Metadata
  last_updated: string;
  region: string;
}

export interface SESIdentityMetrics {
  identity: string;
  identity_type: "EmailAddress" | "Domain";
  verification_status: string;
  dkim_enabled: boolean;
  emails_sent_24h: number;
  emails_sent_7d: number;
  emails_sent_30d: number;
  bounce_rate: number;
  complaint_rate: number;
  last_checked: string;
}

// Cost Intelligence / Inventory types
export type UtilizationStatus = "idle" | "low" | "medium" | "high" | "unknown";
export type OptimizationPriority = "critical" | "high" | "medium" | "low" | "none";

export interface AllCloudResource {
  id: string;
  scan_id: string;
  cloud_account_id: string;
  resource_type: ResourceType;
  resource_id: string;
  resource_name: string | null;
  region: string;
  estimated_monthly_cost: number;
  currency: string;
  utilization_status: UtilizationStatus;
  cpu_utilization_percent: number | null;
  memory_utilization_percent: number | null;
  storage_utilization_percent: number | null;
  network_utilization_mbps: number | null;
  is_optimizable: boolean;
  optimization_priority: OptimizationPriority;
  optimization_score: number;
  potential_monthly_savings: number;
  optimization_recommendations: OptimizationRecommendationItem[] | null;
  resource_metadata: Record<string, any> | null;
  tags: Record<string, string> | null;
  resource_status: string | null;
  is_orphan: boolean;
  created_at_cloud: string | null;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InventoryStats {
  total_resources: number;
  total_monthly_cost: number;
  total_annual_cost: number;
  by_type: Record<string, number>;
  by_region: Record<string, number>;
  by_provider: Record<string, number>;
  by_utilization: Record<string, number>;
  optimizable_resources: number;
  potential_monthly_savings: number;
  potential_annual_savings: number;
  high_cost_resources: number;
}

export interface CostBreakdown {
  by_type: CostBreakdownItem[];
  by_region: CostBreakdownItem[];
  by_provider: CostBreakdownItem[];
  by_tag?: CostBreakdownItem[];
}

export interface CostBreakdownItem {
  name: string;
  count: number;
  total_monthly_cost: number;
  percentage?: number;
}

export interface HighCostResource {
  id: string;
  resource_type: ResourceType;
  resource_name: string | null;
  region: string;
  estimated_monthly_cost: number;
  utilization_status: UtilizationStatus;
  is_optimizable: boolean;
  potential_monthly_savings: number;
  optimization_recommendations: OptimizationRecommendationItem[] | null;
  tags: Record<string, string> | null;
}

export interface OptimizationRecommendationItem {
  resource_id: string;
  resource_type: ResourceType;
  resource_name: string | null;
  current_monthly_cost: number;
  recommended_action: string;
  potential_monthly_savings: number;
  priority: OptimizationPriority;
  details: string;
  alternatives?: Array<{
    name: string;
    cost: number;
    savings: number;
  }>;
}

export interface CostTrend {
  date: string;
  total_cost: number;
  by_provider: Record<string, number>;
  by_type: Record<string, number>;
}

export interface BudgetStatus {
  monthly_budget: number | null;
  current_spend: number;
  projected_monthly_spend: number;
  remaining_budget: number | null;
  budget_utilization_percent: number | null;
  is_over_budget: boolean;
  days_remaining_in_month: number;
}

export interface InventoryFilters {
  cloud_account_id?: string;
  resource_type?: ResourceType;
  is_optimizable?: boolean;
  min_cost?: number;
  skip?: number;
  limit?: number;
}
