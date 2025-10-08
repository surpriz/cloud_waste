"use client";

import { useEffect, useState } from "react";
import { useResourceStore } from "@/stores/useResourceStore";
import { useAccountStore } from "@/stores/useAccountStore";
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
} from "lucide-react";
import type { ResourceStatus, ResourceType } from "@/types";

const resourceIcons: Record<ResourceType, any> = {
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Orphan Resources</h1>
          <p className="mt-2 text-gray-600">
            Review and manage detected orphaned cloud resources
          </p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
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
                <optgroup label="Storage & Compute">
                  <option value="ebs_volume">EBS Volume</option>
                  <option value="ebs_snapshot">EBS Snapshot</option>
                  <option value="ec2_instance">EC2 Instance</option>
                  <option value="fsx_file_system">FSx File System</option>
                </optgroup>
                <optgroup label="Networking">
                  <option value="elastic_ip">Elastic IP</option>
                  <option value="nat_gateway">NAT Gateway</option>
                  <option value="load_balancer">Load Balancer</option>
                  <option value="vpn_connection">VPN Connection</option>
                  <option value="transit_gateway_attachment">Transit Gateway Attachment</option>
                  <option value="vpc_endpoint">VPC Endpoint</option>
                  <option value="global_accelerator">Global Accelerator</option>
                </optgroup>
                <optgroup label="Databases">
                  <option value="rds_instance">RDS Instance</option>
                  <option value="neptune_cluster">Neptune Cluster</option>
                  <option value="redshift_cluster">Redshift Cluster</option>
                  <option value="documentdb_cluster">DocumentDB Cluster</option>
                  <option value="elasticache_cluster">ElastiCache Cluster</option>
                  <option value="opensearch_domain">OpenSearch Domain</option>
                </optgroup>
                <optgroup label="Containers & Streaming">
                  <option value="eks_cluster">EKS Cluster</option>
                  <option value="msk_cluster">MSK Cluster</option>
                  <option value="kinesis_stream">Kinesis Stream</option>
                </optgroup>
                <optgroup label="Machine Learning">
                  <option value="sagemaker_endpoint">SageMaker Endpoint</option>
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
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span>ID: {resource.resource_id}</span>
              </div>

              {/* Orphan reason - why is this resource orphaned? */}
              {resource.resource_metadata?.orphan_reason && (
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
                    <div className="space-y-1 text-sm">
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">✗</span>
                        <span>Database is in stopped state</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
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
                    <div className="space-y-1 text-sm">
                      <div className="flex items-center gap-2 text-red-700">
                        <span className="font-semibold">✗</span>
                        <span>No healthy backend targets</span>
                      </div>
                      <div className="flex items-center gap-2 text-gray-600 mt-1">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
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

                  {/* Generic criteria for other resource types */}
                  {!['ebs_volume', 'elastic_ip', 'rds_instance', 'ec2_instance', 'load_balancer', 'nat_gateway', 'ebs_snapshot'].includes(resource.resource_type) && (
                    <div className="text-sm">
                      <div className="flex items-center gap-2 text-gray-700">
                        <span className="font-semibold">ℹ️</span>
                        <span className="italic">{resource.resource_metadata.orphan_reason}</span>
                      </div>
                    </div>
                  )}

                  <div className="mt-2 pt-2 border-t border-amber-300">
                    <p className="text-xs text-amber-800">
                      💡 <strong>What to do:</strong> Review this resource on your AWS console and delete it if no longer needed to stop wasting money.
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
