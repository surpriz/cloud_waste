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
  regions: { regions: string[] } | null;
  description: string | null;
  is_active: boolean;
  last_scan_at: string | null;
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
  | "virtual_machine_deallocated";

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
