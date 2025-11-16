"use client";

import { useEffect, useState } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { useScanStore } from "@/stores/useScanStore";
import { useResourceStore } from "@/stores/useResourceStore";
import { useAuthStore } from "@/stores/useAuthStore";
import { useInventoryStore } from "@/stores/useInventoryStore";
import {
  Cloud,
  Search,
  DollarSign,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  Sparkles,
  ArrowRight,
  Clock,
  CheckCircle,
  HardDrive,
  Server,
  Camera,
  Wifi,
  Network,
  Database,
  Zap,
  X,
} from "lucide-react";
import {
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";

// Resource type icons mapping
const resourceIcons: Record<string, any> = {
  storage_account_empty: HardDrive,
  managed_disk_unattached: HardDrive,
  virtual_machine_never_started: Server,
  virtual_machine_untagged_orphan: Server,
  virtual_machine_spot_convertible: Server,
  virtual_machine_underutilized: Server,
  disk_snapshot_orphaned: Camera,
  public_ip_unassociated: Wifi,
  ebs_volume: HardDrive,
  elastic_ip: Wifi,
  ebs_snapshot: Camera,
  ec2_instance: Server,
  load_balancer: Network,
  rds_instance: Database,
  nat_gateway: Network,
  s3_bucket: HardDrive,
  lambda_function: Zap,
  dynamodb_table: Database,
};

// Provider colors
const PROVIDER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  aws: { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-300" },
  azure: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-300" },
  gcp: { bg: "bg-red-100", text: "text-red-700", border: "border-red-300" },
};

// Format resource type name
function formatResourceType(type: string): string {
  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Get time ago string
function getTimeAgo(dateString: string | null): string {
  if (!dateString) return "Never";
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  return "Just now";
}

export default function DashboardPage() {
  const { accounts, fetchAccounts } = useAccountStore();
  const { summary, fetchSummary, scans, fetchScans } = useScanStore();
  const { stats, fetchStats, resources, fetchResources } = useResourceStore();
  const { highCostResources, fetchHighCostResources } = useInventoryStore();
  const { user } = useAuthStore();
  const [showWelcome, setShowWelcome] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      // SECURITY: Wait for user to be loaded before fetching data
      // This prevents showing cached data from previous user
      if (!user) {
        setIsLoading(true);
        return;
      }

      setIsLoading(true);
      await Promise.all([fetchAccounts(), fetchSummary(), fetchStats(), fetchScans(), fetchResources()]);
      setIsLoading(false);

      // Show welcome banner if no accounts
      if (accounts.length === 0) {
        setShowWelcome(true);
      }

      // Fetch high-cost resources if accounts exist
      if (accounts.length > 0) {
        fetchHighCostResources(accounts[0].id, 50, 5);
      }
    };
    loadData();
  }, [user, fetchAccounts, fetchSummary, fetchStats, fetchScans, fetchResources, fetchHighCostResources, accounts.length]);

  // Mock trend data for sparklines (would come from API in production)
  const generateSparklineData = (trend: "up" | "down" | "stable") => {
    const baseData = Array.from({ length: 7 }, (_, i) => ({
      value: trend === "up" ? 50 + i * 5 : trend === "down" ? 90 - i * 5 : 60 + Math.random() * 10,
    }));
    return baseData;
  };

  // Calculate provider breakdown
  const providerBreakdown = {
    aws: { count: 0, cost: 0 },
    azure: { count: 0, cost: 0 },
    gcp: { count: 0, cost: 0 },
  };

  resources.forEach((resource) => {
    const account = accounts.find((acc) => acc.id === resource.cloud_account_id);
    if (account && account.provider in providerBreakdown) {
      providerBreakdown[account.provider as keyof typeof providerBreakdown].count++;
      providerBreakdown[account.provider as keyof typeof providerBreakdown].cost +=
        resource.estimated_monthly_cost;
    }
  });

  const pieData = [
    { name: "AWS", value: providerBreakdown.aws.count, color: "#f97316" },
    { name: "Azure", value: providerBreakdown.azure.count, color: "#3b82f6" },
    { name: "GCP", value: providerBreakdown.gcp.count, color: "#ef4444" },
  ].filter((item) => item.value > 0);

  // Get top 5 most expensive resources
  const topOffenders = resources
    .sort((a, b) => b.estimated_monthly_cost - a.estimated_monthly_cost)
    .slice(0, 5);

  // Recent activity
  const recentActivity = [
    ...scans.slice(0, 3).map((scan) => ({
      type: "scan",
      message: `Scan ${scan.status} on ${accounts.find((a) => a.id === scan.cloud_account_id)?.account_name || "Unknown"}`,
      time: scan.completed_at || scan.started_at || scan.created_at,
    })),
    ...accounts.slice(0, 2).map((account) => ({
      type: "account",
      message: `Account "${account.account_name}" added`,
      time: account.created_at,
    })),
  ]
    .sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
    .slice(0, 5);

  const statCards = [
    {
      title: "Cloud Accounts",
      value: accounts.length,
      icon: Cloud,
      gradient: "from-blue-500 to-blue-600",
      bgGradient: "from-blue-50 to-blue-100",
      trend: accounts.length > 0 ? "+1 this week" : "Get started",
      trendType: "up" as const,
      sparkline: generateSparklineData("up"),
    },
    {
      title: "Total Scans",
      value: summary?.total_scans || 0,
      icon: Search,
      gradient: "from-green-500 to-emerald-600",
      bgGradient: "from-green-50 to-emerald-100",
      trend: summary?.completed_scans ? `${summary.completed_scans} completed` : "Run first scan",
      trendType: "stable" as const,
      sparkline: generateSparklineData("stable"),
    },
    {
      title: "Waste Detected",
      value: stats?.total_resources || 0,
      icon: AlertTriangle,
      gradient: "from-orange-500 to-amber-600",
      bgGradient: "from-orange-50 to-amber-100",
      trend: stats?.total_resources ? `In ${Object.keys(stats.by_type || {}).length} types` : "None detected",
      trendType: "down" as const,
      sparkline: generateSparklineData("down"),
    },
    {
      title: "Monthly Waste",
      value: `$${(stats?.total_monthly_cost || 0).toFixed(2)}`,
      icon: DollarSign,
      gradient: "from-red-500 to-pink-600",
      bgGradient: "from-red-50 to-pink-100",
      trend: stats?.total_monthly_cost ? `$${(stats.total_annual_cost || 0).toFixed(0)}/year` : "Track costs",
      trendType: "up" as const,
      sparkline: generateSparklineData("up"),
    },
  ];

  if (isLoading) {
    return (
      <div className="space-y-6 md:space-y-8">
        {/* Loading skeleton */}
        <div className="animate-pulse">
          <div className="h-16 bg-gray-200 rounded-xl mb-6"></div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 bg-gray-200 rounded-2xl"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 md:space-y-8">
      {/* Page header */}
      <div className="relative">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 md:h-12 md:w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 shadow-lg">
            <Sparkles className="h-5 w-5 md:h-6 md:w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl md:text-4xl font-extrabold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Dashboard
            </h1>
            <p className="mt-1 text-gray-600 text-sm md:text-lg">
              Overview of your cloud waste detection
            </p>
          </div>
        </div>
      </div>

      {/* Stats cards with trends and sparklines */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.title}
              className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-6 shadow-lg transition-all hover:shadow-2xl hover:-translate-y-1"
            >
              <div
                className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`}
              ></div>

              <div className="relative z-10">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                      {stat.title}
                    </p>
                    <p className="mt-2 text-3xl font-extrabold text-gray-900">
                      {stat.value}
                    </p>
                  </div>
                  <div className={`rounded-xl bg-gradient-to-br ${stat.gradient} p-3 shadow-md`}>
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                </div>

                {/* Sparkline */}
                <div className="h-8 mb-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={stat.sparkline}>
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#6366f1"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Trend */}
                <div className="flex items-center gap-1 text-xs text-gray-600">
                  {stat.trendType === "up" && <TrendingUp className="h-3 w-3 text-green-600" />}
                  {stat.trendType === "down" && <TrendingDown className="h-3 w-3 text-red-600" />}
                  <span>{stat.trend}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Top row: High-Cost Resources (if available) + Top Offenders + Provider Breakdown */}
      {highCostResources.length > 0 && (
        <div className="rounded-2xl border-2 border-purple-300 bg-gradient-to-br from-purple-50 to-indigo-50 p-6 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-purple-600" />
              💡 Expensive Resources Alert
            </h2>
            <a
              href="/dashboard/cost-intelligence"
              className="text-sm font-semibold text-purple-600 hover:text-purple-700 flex items-center gap-1"
            >
              View All <ArrowRight className="h-4 w-4" />
            </a>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Resources costing more than $50/month - Review for optimization opportunities
          </p>
          <div className="space-y-3">
            {highCostResources.slice(0, 5).map((resource, idx) => {
              const Icon = resourceIcons[resource.resource_type] || HardDrive;
              return (
                <div
                  key={resource.id}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white shadow-sm hover:shadow-md transition-all"
                >
                  <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-purple-100 text-purple-700 font-bold text-sm">
                    {idx + 1}
                  </div>
                  <Icon className="h-5 w-5 text-gray-600 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-gray-900 truncate">
                      {formatResourceType(resource.resource_type)}
                    </p>
                    <p className="text-xs text-gray-600">
                      {resource.region}
                      {resource.is_optimizable && (
                        <span className="ml-2 text-orange-600 font-medium">
                          • Can save ${resource.potential_monthly_savings.toFixed(2)}/mo
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="font-bold text-gray-900">
                      ${resource.estimated_monthly_cost.toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500">/month</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Top Offenders + Provider Breakdown */}
      {stats && stats.total_resources > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Top Offenders */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              Top Offenders (Orphans)
            </h2>
            <div className="space-y-3">
              {topOffenders.length > 0 ? (
                topOffenders.map((resource, idx) => {
                  const Icon = resourceIcons[resource.resource_type] || HardDrive;
                  const account = accounts.find((acc) => acc.id === resource.cloud_account_id);
                  const provider = (account?.provider || "aws") as keyof typeof PROVIDER_COLORS;
                  const providerColors = PROVIDER_COLORS[provider];

                  return (
                    <div
                      key={resource.id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-gray-50 to-gray-100 hover:from-orange-50 hover:to-amber-50 transition-all"
                    >
                      <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-orange-100 text-orange-700 font-bold text-sm">
                        {idx + 1}
                      </div>
                      <Icon className="h-5 w-5 text-gray-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm text-gray-900 truncate">
                          {formatResourceType(resource.resource_type)}
                        </p>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${providerColors.bg} ${providerColors.text}`}
                        >
                          {account?.provider.toUpperCase()}
                        </span>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="font-bold text-gray-900">
                          ${resource.estimated_monthly_cost.toFixed(2)}
                        </p>
                        <p className="text-xs text-gray-500">/month</p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-center text-gray-500 py-8">No resources detected yet</p>
              )}
            </div>
          </div>

          {/* Provider Breakdown */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Cloud className="h-5 w-5 text-blue-600" />
              Provider Breakdown
            </h2>
            {pieData.length > 0 ? (
              <div className="flex items-center gap-6">
                <div className="flex-1">
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-3">
                  {Object.entries(providerBreakdown).map(([provider, data]) => {
                    if (data.count === 0) return null;
                    const providerKey = provider as keyof typeof PROVIDER_COLORS;
                    const colors = PROVIDER_COLORS[providerKey];
                    return (
                      <div key={provider} className="flex items-center gap-3">
                        <div
                          className={`w-3 h-3 rounded-full ${
                            provider === "aws"
                              ? "bg-orange-500"
                              : provider === "azure"
                              ? "bg-blue-500"
                              : "bg-red-500"
                          }`}
                        ></div>
                        <div>
                          <p className="font-semibold text-gray-900 text-sm">
                            {provider.toUpperCase()}
                          </p>
                          <p className="text-xs text-gray-600">
                            {data.count} resources • ${data.cost.toFixed(2)}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="text-center text-gray-500 py-8">
                Connect accounts to see breakdown
              </p>
            )}
          </div>
        </div>
      )}

      {/* Resources by Type - Improved */}
      {stats && stats.by_type && Object.keys(stats.by_type).length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Resources by Type</h2>
            <a
              href="/dashboard/resources"
              className="text-sm font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              View All <ArrowRight className="h-4 w-4" />
            </a>
          </div>
          <div className="space-y-4">
            {Object.entries(stats.by_type)
              .slice(0, 10)
              .map(([type, count]) => {
                const Icon = resourceIcons[type] || HardDrive;
                const totalResources = stats.total_resources || 1;
                const percentage = (Number(count) / totalResources) * 100;

                // Calculate cost for this type
                const typeCost = resources
                  .filter((r) => r.resource_type === type)
                  .reduce((sum, r) => sum + r.estimated_monthly_cost, 0);

                // Get provider for this resource type
                const firstResource = resources.find((r) => r.resource_type === type);
                const account = accounts.find((acc) => acc.id === firstResource?.cloud_account_id);
                const provider = (account?.provider || "aws") as keyof typeof PROVIDER_COLORS;
                const providerColors = PROVIDER_COLORS[provider];

                return (
                  <div key={type} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1">
                        <Icon className="h-5 w-5 text-gray-600 flex-shrink-0" />
                        <span className="font-semibold text-gray-700 text-sm">
                          {formatResourceType(type)}
                        </span>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${providerColors.bg} ${providerColors.text}`}
                        >
                          {account?.provider.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm text-gray-600">{count} resources</span>
                        <span className="font-bold text-gray-900 min-w-[80px] text-right">
                          ${typeCost.toFixed(2)}/mo
                        </span>
                      </div>
                    </div>
                    {/* Progress bar */}
                    <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="absolute h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full transition-all"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                    <p className="text-xs text-gray-500">{percentage.toFixed(1)}% of total waste</p>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Quick Actions</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <a
            href="/dashboard/accounts"
            className="group relative overflow-hidden rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100 p-6 transition-all hover:border-blue-500 hover:shadow-xl hover:-translate-y-1"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-blue-600 p-2">
                <Cloud className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-900 group-hover:text-blue-700 transition-colors">
                  Add Cloud Account
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Connect your AWS, Azure, or GCP account
                </p>
                {accounts.length > 0 && (
                  <div className="mt-3 inline-flex items-center px-2 py-1 rounded-md bg-blue-200 text-blue-800 text-xs font-semibold">
                    {accounts.length} connected
                  </div>
                )}
              </div>
            </div>
          </a>
          <a
            href="/dashboard/scans"
            className="group relative overflow-hidden rounded-xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-emerald-100 p-6 transition-all hover:border-green-500 hover:shadow-xl hover:-translate-y-1"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-green-600 p-2">
                <Search className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-900 group-hover:text-green-700 transition-colors">
                  Run New Scan
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Detect orphaned resources in your cloud
                </p>
                {summary?.last_scan_at && (
                  <div className="mt-3 inline-flex items-center px-2 py-1 rounded-md bg-green-200 text-green-800 text-xs font-semibold">
                    Last: {getTimeAgo(summary.last_scan_at)}
                  </div>
                )}
              </div>
            </div>
          </a>
          <a
            href="/dashboard/resources"
            className="group relative overflow-hidden rounded-xl border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-amber-100 p-6 transition-all hover:border-orange-500 hover:shadow-xl hover:-translate-y-1"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-orange-600 p-2">
                <AlertTriangle className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-900 group-hover:text-orange-700 transition-colors">
                  View Resources
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Manage detected orphaned resources
                </p>
                {stats && stats.total_resources > 0 && (
                  <div className="mt-3 inline-flex items-center px-2 py-1 rounded-md bg-orange-200 text-orange-800 text-xs font-semibold">
                    {stats.total_resources} detected
                  </div>
                )}
              </div>
            </div>
          </a>
        </div>
      </div>

      {/* Recent Activity */}
      {recentActivity.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Clock className="h-5 w-5 text-gray-600" />
            Recent Activity
          </h2>
          <div className="space-y-4">
            {recentActivity.map((activity, idx) => (
              <div key={idx} className="flex items-start gap-4">
                <div
                  className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full ${
                    activity.type === "scan" ? "bg-green-100" : "bg-blue-100"
                  }`}
                >
                  {activity.type === "scan" ? (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  ) : (
                    <Cloud className="h-4 w-4 text-blue-600" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{activity.message}</p>
                  <p className="text-xs text-gray-500">{getTimeAgo(activity.time)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Annual savings estimate */}
      {stats && stats.total_monthly_cost > 0 && (
        <div className="relative overflow-hidden rounded-2xl border-2 border-green-300 bg-gradient-to-br from-green-50 to-emerald-100 p-8 shadow-xl">
          <div className="absolute top-0 right-0 h-40 w-40 bg-green-300 rounded-full blur-3xl opacity-20"></div>

          <div className="relative z-10 flex items-center gap-6">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-green-600 to-emerald-600 shadow-lg">
              <TrendingDown className="h-10 w-10 text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-green-900 mb-2">
                Potential Annual Savings
              </h3>
              <p className="text-5xl font-extrabold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                ${(stats.total_annual_cost || 0).toFixed(2)}
              </p>
              <p className="mt-2 text-green-700 font-medium">
                💰 By removing all detected orphaned resources
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
