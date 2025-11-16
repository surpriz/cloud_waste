"use client";

import { useEffect, useState } from "react";
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
  RefreshCw,
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
    optimizableResources,
    isLoading,
    error,
    fetchStats,
    fetchCostBreakdown,
    fetchHighCostResources,
    fetchOptimizableResources,
  } = useInventoryStore();

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [minCostFilter, setMinCostFilter] = useState<number>(100);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  useEffect(() => {
    if (accounts.length > 0 && !selectedAccountId) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  useEffect(() => {
    if (selectedAccountId) {
      fetchStats(selectedAccountId);
      fetchCostBreakdown(selectedAccountId);
      fetchHighCostResources(selectedAccountId, minCostFilter, 10);
      fetchOptimizableResources(selectedAccountId, 20);
    }
  }, [
    selectedAccountId,
    minCostFilter,
    fetchStats,
    fetchCostBreakdown,
    fetchHighCostResources,
    fetchOptimizableResources,
  ]);

  const handleRefresh = () => {
    if (selectedAccountId) {
      fetchStats(selectedAccountId);
      fetchCostBreakdown(selectedAccountId);
      fetchHighCostResources(selectedAccountId, minCostFilter, 10);
      fetchOptimizableResources(selectedAccountId, 20);
    }
  };

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
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Cost Intelligence
            </h1>
            <p className="mt-1 text-gray-600 text-lg">
              Complete view of all your cloud resources and costs - data updated automatically when you run a scan
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
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-700">
          {error}
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

      {/* Optimization Opportunities */}
      {optimizableResources.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              Optimization Opportunities
            </h2>
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-green-100 text-green-800 text-sm font-semibold">
              {optimizableResources.length} resources
            </span>
          </div>
          <div className="space-y-4">
            {optimizableResources.slice(0, 10).map((resource) => {
              const Icon = resourceIcons[resource.resource_type] || Server;
              const savingsPercentage =
                (resource.potential_monthly_savings /
                  resource.estimated_monthly_cost) *
                100;
              return (
                <div
                  key={resource.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-5 w-5 text-gray-600" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-gray-900">
                          {resource.resource_name ||
                            formatResourceType(resource.resource_type)}
                        </p>
                        {/* Priority Badge */}
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                            resource.optimization_priority === "critical"
                              ? "bg-red-100 text-red-700"
                              : resource.optimization_priority === "high"
                              ? "bg-orange-100 text-orange-700"
                              : "bg-yellow-100 text-yellow-700"
                          }`}
                        >
                          {resource.optimization_priority.toUpperCase()}
                        </span>
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
                    <p className="text-lg font-bold text-green-600">
                      Save ${resource.potential_monthly_savings.toFixed(2)}/mo
                    </p>
                    <p className="text-xs text-gray-500">
                      (-{savingsPercentage.toFixed(0)}%)
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
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
            Run a scan to discover your cloud resources and costs.
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
