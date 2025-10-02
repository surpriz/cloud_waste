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
                <option value="ebs_volume">EBS Volume</option>
                <option value="elastic_ip">Elastic IP</option>
                <option value="ebs_snapshot">EBS Snapshot</option>
                <option value="ec2_instance">EC2 Instance</option>
                <option value="load_balancer">Load Balancer</option>
                <option value="rds_instance">RDS Instance</option>
                <option value="nat_gateway">NAT Gateway</option>
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
              {resource.resource_type.replace(/_/g, " ").toUpperCase()} "{" "}
              {resource.region}
            </p>
            <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
              <span>ID: {resource.resource_id}</span>
              <span>"</span>
              <span className="font-semibold text-orange-600">
                ${resource.estimated_monthly_cost.toFixed(2)}/month
              </span>
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
