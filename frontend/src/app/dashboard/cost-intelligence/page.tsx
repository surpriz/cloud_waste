"use client";

import React, { useEffect, useState } from "react";
import { useInventoryStore } from "@/stores/useInventoryStore";
import { useAccountStore } from "@/stores/useAccountStore";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  BarChart3,
  PieChart,
  Sparkles,
  Filter,
  Download,
  HardDrive,
  Server,
  Database,
  Network,
  Zap,
  Monitor,
  Globe,
  Inbox,
  Search,
  Shield,
  Box,
  Workflow,
  FileText,
  GitBranch,
  Upload,
  Users,
  MessageSquare,
  Radio,
  Activity,
  ScanText,
  Eye,
  Smile,
  FileType,
  Mic,
  Bot,
  Brain,
  Key,
  Bell,
  Archive,
  Boxes,
  Cpu,
  Package,
  Cable,
  FileCode,
} from "lucide-react";
import {
  PieChart as RechartsPie,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import type { ResourceType } from "@/types";

// Resource type icons
const resourceIcons: Record<ResourceType, any> = {
  ebs_volume: HardDrive,
  elastic_ip: Network,
  ebs_snapshot: HardDrive,
  ec2_instance: Server,
  load_balancer: Network,
  rds_instance: Database,
  nat_gateway: Network,
  s3_bucket: HardDrive,
  lambda_function: Zap,
  dynamodb_table: Database,
  eks_cluster: Server,
  fargate_task: Server,
  elasticache_cluster: Database,
  kinesis_stream: Zap,
  fsx_file_system: HardDrive,
  opensearch_domain: Search,
  api_gateway: Globe,
  cloudfront_distribution: Globe,
  ecs_cluster: Server,
  cloudwatch_log_group: FileText,
  vpc_endpoint: Network,
  neptune_cluster: Database,
  msk_cluster: Activity,
  sagemaker_endpoint: Activity,
  redshift_cluster: Database,
  vpn_connection: Network,
  transit_gateway_attachment: Network,
  global_accelerator: Network,
  documentdb_cluster: Database,
  ecr_repository: Box,
  sns_topic: Bell,
  sqs_queue: Inbox,
  secrets_manager_secret: Key,
  backup_vault: Archive,
  app_runner_service: Boxes,
  emr_cluster: Cpu,
  sagemaker_notebook: Brain,
  transfer_family_server: Upload,
  elastic_beanstalk_environment: Package,
  direct_connect_connection: Cable,
  mq_broker: MessageSquare,
  kendra_index: Search,
  cloudformation_stack: FileCode,
  // Azure - Cost Intelligence (Inventory mode)
  azure_vm: Server,
  azure_managed_disk: HardDrive,
  azure_public_ip: Network,
  azure_load_balancer: Network,
  azure_app_gateway: Network,
  azure_storage_account: HardDrive,
  azure_expressroute_circuit: Network,
  azure_disk_snapshot: HardDrive,
  azure_nat_gateway: Network,
  azure_sql_database: Database,
  azure_aks_cluster: Server,
  azure_function_app: Zap,
  azure_cosmos_db: Database,
  azure_container_app: Server,
  azure_virtual_desktop: Monitor,
  azure_hdinsight_cluster: BarChart3,
  azure_ml_compute: Sparkles,
  azure_app_service: Globe,
  azure_redis_cache: Database,
  azure_event_hub: Inbox,
  azure_netapp_files: HardDrive,
  azure_cognitive_search: Search,
  azure_api_management: Shield,
  azure_cdn: Globe,
  azure_container_instance: Box,
  azure_logic_app: Workflow,
  azure_log_analytics: FileText,
  azure_backup_vault: Shield,
  azure_data_factory_pipeline: GitBranch,
  azure_synapse_serverless_sql: BarChart3,
  azure_storage_sftp: Upload,
  azure_ad_domain_services: Users,
  azure_service_bus_premium: MessageSquare,
  azure_iot_hub: Radio,
  azure_stream_analytics: Activity,
  azure_document_intelligence: ScanText,
  azure_computer_vision: Eye,
  azure_face_api: Smile,
  azure_text_analytics: FileType,
  azure_speech_services: Mic,
  azure_bot_service: Bot,
  azure_application_insights: Activity,
  azure_managed_devops_pools: Workflow,
  azure_private_endpoint: Network,
  azure_cosmos_db_gremlin: Database,
  azure_hdinsight_kafka: Server,
  azure_ml_endpoint: Brain,
  azure_synapse_sql_pool: BarChart3,
  azure_vpn_gateway: Shield,
  azure_vnet_peering: GitBranch,
  azure_front_door: Globe,
  azure_cosmos_db_mongodb: Inbox,
  azure_container_registry: Box,
  azure_service_bus_topic: Radio,
  azure_service_bus_queue: MessageSquare,
  azure_event_grid_subscription: Zap,
  azure_key_vault_secret: Key,
  azure_app_configuration: FileText,
  azure_api_management: Globe,
  azure_logic_app: Workflow,
  azure_data_factory: Database,
  azure_static_web_app: Globe,
  azure_dedicated_hsm: Shield,
  azure_iot_hub_routing: Radio,
  azure_ml_online_endpoint: Brain,
  azure_ml_batch_endpoint: BarChart3,
  azure_automation_account: Workflow,
  azure_advisor_recommendation: Sparkles,
  azure_arm_deployment: FileText,
  azure_container_instance: Box,
  azure_batch_job: Zap,
  azure_storage_lifecycle_policy: Database,
  // Add more as needed (truncated for brevity)
} as any;

// Provider colors
const PROVIDER_COLORS: Record<string, string> = {
  aws: "#FF9900",
  azure: "#0078D4",
  gcp: "#4285F4",
};

// Format resource type name
function formatResourceType(type: string): string {
  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function CostIntelligencePage() {
  const { accounts, fetchAccounts } = useAccountStore();
  const {
    stats,
    costBreakdown,
    highCostResources,
    allResources,
    isLoading,
    error,
    fetchStats,
    fetchCostBreakdown,
    fetchHighCostResources,
    fetchAllResources,
  } = useInventoryStore();

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [minCostFilter, setMinCostFilter] = useState<number>(100);
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>("all");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  useEffect(() => {
    if (accounts.length > 0 && !selectedAccountId) {
      // Prioritize accounts with better inventory support
      // Azure has the most comprehensive scanning (60+ resource types)
      const providerPriority: Record<string, number> = {
        azure: 1,
        aws: 2,
        gcp: 3,
        microsoft365: 4
      };
      const sortedAccounts = [...accounts].sort((a, b) =>
        (providerPriority[a.provider] || 5) - (providerPriority[b.provider] || 5)
      );
      setSelectedAccountId(sortedAccounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  useEffect(() => {
    if (selectedAccountId) {
      fetchStats(selectedAccountId);
      fetchCostBreakdown(selectedAccountId);
      fetchHighCostResources(selectedAccountId, minCostFilter, 10);
      fetchAllResources({
        cloud_account_id: selectedAccountId,
        limit: 100,
      });
    }
  }, [
    selectedAccountId,
    minCostFilter,
    fetchStats,
    fetchCostBreakdown,
    fetchHighCostResources,
    fetchAllResources,
  ]);

  // Get resource color based on status
  const getResourceColor = (resource: any) => {
    if (resource.is_orphan) {
      return {
        bg: "from-red-50 to-rose-50",
        border: "border-red-200",
        badge: "bg-red-100 text-red-700",
        label: "Orphan (Waste)",
      };
    } else if (resource.is_optimizable) {
      return {
        bg: "from-orange-50 to-amber-50",
        border: "border-orange-200",
        badge: "bg-orange-100 text-orange-700",
        label: "Optimizable",
      };
    } else {
      return {
        bg: "from-green-50 to-emerald-50",
        border: "border-green-200",
        badge: "bg-green-100 text-green-700",
        label: "Optimized",
      };
    }
  };

  // Filter resources based on priority and type
  // IMPORTANT: Exclude orphan resources (they are shown in Waste Detection tab)
  const filteredResources = React.useMemo(() => {
    // First, exclude orphan resources (waste) - they belong in Waste Detection tab
    let filtered = allResources.filter((resource) => !resource.is_orphan);

    // Filter by priority
    if (priorityFilter !== "all") {
      filtered = filtered.filter(
        (resource) => resource.optimization_priority === priorityFilter
      );
    }

    // Filter by resource type
    if (resourceTypeFilter !== "all") {
      filtered = filtered.filter(
        (resource) => resource.resource_type === resourceTypeFilter
      );
    }

    return filtered;
  }, [allResources, priorityFilter, resourceTypeFilter]);

  // Get unique resource types for filter dropdown (excluding orphan resources)
  const uniqueResourceTypes = React.useMemo(() => {
    const nonOrphanResources = allResources.filter((r) => !r.is_orphan);
    const types = new Set(nonOrphanResources.map((r) => r.resource_type));
    return Array.from(types).sort();
  }, [allResources]);

  if (isLoading && !stats) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 md:space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 shadow-lg">
            <Sparkles className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent flex items-center gap-2">
              <span className="text-4xl">💡</span> Cost Optimization Hub
            </h1>
            <p className="mt-1 text-gray-600 text-lg">
              Discover cost-saving opportunities across ALL your cloud infrastructure
            </p>
            <p className="mt-1 text-sm text-blue-600 font-medium">
              💡 Note: Orphaned resources (waste) are shown in Waste Detection tab
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedAccountId}
            onChange={(e) => setSelectedAccountId(e.target.value)}
            className="rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.account_name} ({account.provider.toUpperCase()})
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
          >
            <Filter className="h-5 w-5" />
            Filters
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-700">
          {error}
        </div>
      )}

      {/* Filters Panel */}
      {showFilters && (
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="font-semibold text-gray-900">Filters</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {/* Priority Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Priority
              </label>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            {/* Resource Type Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Resource Type
              </label>
              <select
                value={resourceTypeFilter}
                onChange={(e) => setResourceTypeFilter(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Types</option>
                {uniqueResourceTypes.map((type) => (
                  <option key={type} value={type}>
                    {formatResourceType(type)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  Total Resources
                </p>
                <p className="mt-2 text-3xl font-extrabold text-gray-900">
                  {stats.total_resources}
                </p>
              </div>
              <div className="rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 p-3 shadow-md">
                <Server className="h-6 w-6 text-white" />
              </div>
            </div>
            <p className="text-xs text-gray-600">
              {stats.optimizable_resources} optimizable
            </p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  Monthly Cost
                </p>
                <p className="mt-2 text-3xl font-extrabold text-gray-900">
                  ${stats.total_monthly_cost.toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 p-3 shadow-md">
                <DollarSign className="h-6 w-6 text-white" />
              </div>
            </div>
            <p className="text-xs text-gray-600">
              ${stats.total_annual_cost.toFixed(2)}/year
            </p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  Potential Savings
                </p>
                <p className="mt-2 text-3xl font-extrabold text-gray-900">
                  ${stats.potential_monthly_savings.toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 p-3 shadow-md">
                <TrendingDown className="h-6 w-6 text-white" />
              </div>
            </div>
            <p className="text-xs text-gray-600">
              ${stats.potential_annual_savings.toFixed(2)}/year
            </p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  High Cost Resources
                </p>
                <p className="mt-2 text-3xl font-extrabold text-gray-900">
                  {stats.high_cost_resources}
                </p>
              </div>
              <div className="rounded-xl bg-gradient-to-br from-red-500 to-pink-600 p-3 shadow-md">
                <AlertTriangle className="h-6 w-6 text-white" />
              </div>
            </div>
            <p className="text-xs text-gray-600">&gt;${minCostFilter}/month</p>
          </div>
        </div>
      )}

      {/* High Cost Resources Alert */}
      {highCostResources.length > 0 && (
        <div className="rounded-2xl border-2 border-orange-300 bg-gradient-to-br from-orange-50 to-amber-50 p-8 shadow-lg">
          <div className="flex items-center gap-3 mb-6">
            <AlertTriangle className="h-6 w-6 text-orange-600" />
            <h2 className="text-2xl font-bold text-gray-900">
              High-Cost Resources Alert
            </h2>
          </div>
          <div className="space-y-3">
            {highCostResources.map((resource) => {
              const Icon = resourceIcons[resource.resource_type] || Server;
              return (
                <div
                  key={resource.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-white shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-5 w-5 text-gray-600" />
                    <div>
                      <p className="font-semibold text-gray-900">
                        {resource.resource_name ||
                          formatResourceType(resource.resource_type)}
                      </p>
                      <p className="text-sm text-gray-600">
                        {resource.region} •{" "}
                        <span
                          className={`font-medium ${
                            resource.is_optimizable
                              ? "text-orange-600"
                              : "text-green-600"
                          }`}
                        >
                          {resource.is_optimizable
                            ? "Optimizable"
                            : "Optimized"}
                        </span>
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">
                      ${resource.estimated_monthly_cost.toFixed(2)}
                    </p>
                    <p className="text-sm text-gray-600">/month</p>
                    {resource.is_optimizable &&
                      resource.potential_monthly_savings > 0 && (
                        <p className="text-sm text-green-600 font-medium">
                          Save ${resource.potential_monthly_savings.toFixed(2)}
                          /mo
                        </p>
                      )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cost Breakdown */}
      {costBreakdown && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* By Type */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Cost by Resource Type
            </h3>
            <div className="space-y-3">
              {costBreakdown.by_type.slice(0, 8).map((item: any) => {
                const percentage =
                  (item.total_monthly_cost / (stats?.total_monthly_cost || 1)) *
                  100;
                return (
                  <div key={item.resource_type || item.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-700">
                        {formatResourceType(item.resource_type || item.name)}
                      </span>
                      <span className="text-sm font-bold text-gray-900">
                        ${item.total_monthly_cost.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full transition-all"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {item.count} resources • {percentage.toFixed(1)}%
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* By Region */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Cost by Region
            </h3>
            <div className="space-y-3">
              {costBreakdown.by_region.slice(0, 8).map((item: any) => {
                const percentage =
                  (item.total_monthly_cost / (stats?.total_monthly_cost || 1)) *
                  100;
                return (
                  <div key={item.region || item.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-700">
                        {item.region || item.name}
                      </span>
                      <span className="text-sm font-bold text-gray-900">
                        ${item.total_monthly_cost.toFixed(2)}
                      </span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-green-500 to-emerald-600 rounded-full transition-all"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {item.count} resources • {percentage.toFixed(1)}%
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* All Resources with Filters */}
      {allResources.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              Cost Optimization Opportunities
            </h2>
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-sm font-semibold">
              {filteredResources.length} of {allResources.filter(r => !r.is_orphan).length} resources
            </span>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-4 mb-6">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">Filters:</span>
            </div>

            {/* Priority Filter */}
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="none">None</option>
            </select>

            {/* Resource Type Filter */}
            <select
              value={resourceTypeFilter}
              onChange={(e) => setResourceTypeFilter(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              {uniqueResourceTypes.map((type) => (
                <option key={type} value={type}>
                  {formatResourceType(type)}
                </option>
              ))}
            </select>

            {/* Reset Filters */}
            {(priorityFilter !== "all" || resourceTypeFilter !== "all") && (
              <button
                onClick={() => {
                  setPriorityFilter("all");
                  setResourceTypeFilter("all");
                }}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                Reset Filters
              </button>
            )}
          </div>

          {/* Color Legend */}
          <div className="flex items-center gap-6 mb-6 p-4 bg-gray-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Legend:</span>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded"></div>
              <span className="text-sm text-gray-600">Optimized (no savings)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-200 rounded"></div>
              <span className="text-sm text-gray-600">Optimizable (potential savings)</span>
            </div>
          </div>

          {/* Resources List */}
          <div className="space-y-4">
            {filteredResources.slice(0, 20).map((resource) => {
              const Icon = resourceIcons[resource.resource_type] || Server;
              const colors = getResourceColor(resource);
              const savingsPercentage = resource.potential_monthly_savings > 0
                ? (resource.potential_monthly_savings / resource.estimated_monthly_cost) * 100
                : 0;

              return (
                <div
                  key={resource.id}
                  className={`flex items-center justify-between p-4 rounded-xl bg-gradient-to-r ${colors.bg} border-2 ${colors.border} hover:shadow-md transition-shadow`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-5 w-5 text-gray-600" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-gray-900">
                          {resource.resource_name ||
                            formatResourceType(resource.resource_type)}
                        </p>

                        {/* Status Badge */}
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${colors.badge}`}>
                          {colors.label}
                        </span>

                        {/* Priority Badge */}
                        {resource.optimization_priority && resource.optimization_priority !== "none" && (
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                              resource.optimization_priority === "critical"
                                ? "bg-red-100 text-red-700"
                                : resource.optimization_priority === "high"
                                ? "bg-orange-100 text-orange-700"
                                : resource.optimization_priority === "medium"
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-blue-100 text-blue-700"
                            }`}
                          >
                            {resource.optimization_priority.toUpperCase()}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        {resource.region}
                      </p>

                      {/* Optimization Recommendation */}
                      {resource.optimization_recommendations &&
                        resource.optimization_recommendations.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <p className="text-sm font-medium text-gray-700">
                              💡 {resource.optimization_recommendations[0].action}
                            </p>
                            <p className="text-xs text-gray-600">
                              {resource.optimization_recommendations[0].details}
                            </p>
                          </div>
                        )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">
                      Current: ${resource.estimated_monthly_cost.toFixed(2)}/mo
                    </p>
                    {resource.potential_monthly_savings > 0 ? (
                      <>
                        <p className="text-lg font-bold text-green-600">
                          Save ${resource.potential_monthly_savings.toFixed(2)}/mo
                        </p>
                        <p className="text-xs text-gray-500">
                          (-{savingsPercentage.toFixed(0)}%)
                        </p>
                      </>
                    ) : (
                      <p className="text-lg font-bold text-green-600">
                        ✓ Optimized
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Show More Button */}
          {filteredResources.length > 20 && (
            <div className="mt-6 text-center">
              <p className="text-sm text-gray-600">
                Showing 20 of {filteredResources.length} resources
              </p>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && stats && stats.total_resources === 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-12 text-center shadow-lg">
          <BarChart3 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            No Resources Found
          </h3>
          <p className="text-gray-600 mb-6">
            No resources found for this account.
            {accounts.length > 1 && (
              <span className="block mt-2">
                Try selecting a different account above, or run a scan to discover resources.
              </span>
            )}
            {accounts.length === 1 && (
              <span className="block mt-2">
                Run a scan to discover your cloud resources and costs.
              </span>
            )}
          </p>
          <a
            href="/dashboard/scans"
            className="inline-flex items-center px-6 py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors"
          >
            Run Your First Scan
          </a>
        </div>
      )}
    </div>
  );
}
