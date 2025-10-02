"use client";

import { useEffect } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { useScanStore } from "@/stores/useScanStore";
import { useResourceStore } from "@/stores/useResourceStore";
import { Cloud, Search, DollarSign, AlertTriangle, TrendingDown, Sparkles } from "lucide-react";

export default function DashboardPage() {
  const { accounts, fetchAccounts } = useAccountStore();
  const { summary, fetchSummary } = useScanStore();
  const { stats, fetchStats } = useResourceStore();

  useEffect(() => {
    fetchAccounts();
    fetchSummary();
    fetchStats();
  }, [fetchAccounts, fetchSummary, fetchStats]);

  const statCards = [
    {
      title: "Cloud Accounts",
      value: accounts.length,
      icon: Cloud,
      gradient: "from-blue-500 to-blue-600",
      bgGradient: "from-blue-50 to-blue-100",
    },
    {
      title: "Total Scans",
      value: summary?.total_scans || 0,
      icon: Search,
      gradient: "from-green-500 to-emerald-600",
      bgGradient: "from-green-50 to-emerald-100",
    },
    {
      title: "Orphan Resources",
      value: stats?.total_resources || 0,
      icon: AlertTriangle,
      gradient: "from-orange-500 to-amber-600",
      bgGradient: "from-orange-50 to-amber-100",
    },
    {
      title: "Monthly Waste",
      value: `$${(stats?.total_monthly_cost || 0).toFixed(2)}`,
      icon: DollarSign,
      gradient: "from-red-500 to-pink-600",
      bgGradient: "from-red-50 to-pink-100",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="relative">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 shadow-lg">
            <Sparkles className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Dashboard
            </h1>
            <p className="mt-1 text-gray-600 text-lg">
              Overview of your cloud waste detection
            </p>
          </div>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.title}
              className="group relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-6 shadow-lg transition-all hover:shadow-2xl hover:-translate-y-1"
            >
              <div className={`absolute inset-0 bg-gradient-to-br ${stat.bgGradient} opacity-0 group-hover:opacity-100 transition-opacity`}></div>

              <div className="relative z-10">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 uppercase tracking-wide group-hover:text-gray-700">
                      {stat.title}
                    </p>
                    <p className="mt-3 text-4xl font-extrabold text-gray-900">
                      {stat.value}
                    </p>
                  </div>
                  <div className={`rounded-xl bg-gradient-to-br ${stat.gradient} p-3 shadow-md`}>
                    <Icon className="h-7 w-7 text-white" />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Cost breakdown */}
      {stats && stats.by_type && Object.keys(stats.by_type).length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            Resources by Type
          </h2>
          <div className="space-y-4">
            {Object.entries(stats.by_type).map(([type, count]) => (
              <div
                key={type}
                className="group flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-gray-50 to-gray-100 hover:from-blue-50 hover:to-purple-50 transition-all"
              >
                <span className="font-semibold text-gray-700 group-hover:text-blue-700 transition-colors">
                  {type.replace(/_/g, " ").toUpperCase()}
                </span>
                <span className="px-4 py-1 bg-white rounded-lg font-bold text-gray-900 shadow-sm">
                  {count}
                </span>
              </div>
            ))}
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
              <div>
                <h3 className="font-bold text-gray-900 group-hover:text-blue-700 transition-colors">
                  Add Cloud Account
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Connect your AWS account to start scanning
                </p>
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
              <div>
                <h3 className="font-bold text-gray-900 group-hover:text-green-700 transition-colors">
                  Run New Scan
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Detect orphaned resources in your cloud
                </p>
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
              <div>
                <h3 className="font-bold text-gray-900 group-hover:text-orange-700 transition-colors">
                  View Resources
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  Manage detected orphaned resources
                </p>
              </div>
            </div>
          </a>
        </div>
      </div>

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
