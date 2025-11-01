"use client";

import { useEffect, useState } from "react";
import { adminAPI } from "@/lib/api";
import type { PricingStats, PricingCacheItem } from "@/types";
import {
  DollarSign,
  RefreshCw,
  Database,
  CheckCircle,
  AlertCircle,
  Clock,
  TrendingUp,
  Filter,
} from "lucide-react";

export default function AdminPricingPage() {
  const [stats, setStats] = useState<PricingStats | null>(null);
  const [cacheItems, setCacheItems] = useState<PricingCacheItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshTaskId, setRefreshTaskId] = useState<string | null>(null);

  // Filters
  const [providerFilter, setProviderFilter] = useState<string>("");
  const [regionFilter, setRegionFilter] = useState<string>("");

  useEffect(() => {
    loadData();
  }, [providerFilter, regionFilter]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [statsData, cacheData] = await Promise.all([
        adminAPI.getPricingStats(),
        adminAPI.getPricingCache(
          providerFilter || undefined,
          regionFilter || undefined,
          undefined,
          0,
          100
        ),
      ]);
      setStats(statsData);
      setCacheItems(cacheData);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load pricing data");
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshPricing = async () => {
    try {
      setRefreshing(true);
      setError(null);
      const response = await adminAPI.refreshPricing();
      setRefreshTaskId(response.task_id);

      // Poll for task status
      if (response.task_id) {
        pollTaskStatus(response.task_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to trigger pricing refresh");
      setRefreshing(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const maxAttempts = 60; // 60 seconds max
    let attempts = 0;

    const poll = async () => {
      try {
        const status = await adminAPI.getRefreshTaskStatus(taskId);

        if (status.status === "success") {
          setRefreshing(false);
          setRefreshTaskId(null);
          await loadData(); // Reload data
          alert(`Pricing refresh completed! Updated: ${status.updated_count}, Failed: ${status.failed_count}`);
        } else if (status.status === "error") {
          setRefreshing(false);
          setRefreshTaskId(null);
          setError(`Refresh failed: ${status.message}`);
        } else if (attempts < maxAttempts) {
          attempts++;
          setTimeout(poll, 1000); // Poll every second
        } else {
          setRefreshing(false);
          setRefreshTaskId(null);
          setError("Refresh task timeout - check manually");
        }
      } catch (err: any) {
        setRefreshing(false);
        setRefreshTaskId(null);
        setError(err.message);
      }
    };

    poll();
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatTimeSince = (dateString: string | null) => {
    if (!dateString) return "Never";
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

    if (diffHours > 24) {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
    } else if (diffHours > 0) {
      return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    } else {
      return `${diffMinutes} minute${diffMinutes > 1 ? "s" : ""} ago`;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading pricing management...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <DollarSign className="h-8 w-8 text-green-600" />
                <h1 className="text-3xl font-bold text-gray-900">
                  Pricing Management
                </h1>
              </div>
              <p className="text-gray-600">
                Monitor and manage dynamic cloud pricing system
              </p>
            </div>
            <button
              onClick={handleRefreshPricing}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw
                className={`h-5 w-5 ${refreshing ? "animate-spin" : ""}`}
              />
              {refreshing ? "Refreshing..." : "Refresh Prices Now"}
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            {error}
          </div>
        )}

        {/* Statistics Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Total Cached Prices
                  </p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">
                    {stats.total_cached_prices}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {stats.expired_prices} expired
                  </p>
                </div>
                <Database className="h-12 w-12 text-blue-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Last Refresh
                  </p>
                  <p className="text-xl font-bold text-gray-900 mt-2">
                    {formatTimeSince(stats.last_refresh_at)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {stats.last_refresh_at
                      ? formatDate(stats.last_refresh_at)
                      : "Never refreshed"}
                  </p>
                </div>
                <Clock className="h-12 w-12 text-orange-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Cache Hit Rate
                  </p>
                  <p className="text-3xl font-bold text-green-600 mt-2">
                    {stats.cache_hit_rate.toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {stats.total_cached_prices - stats.expired_prices} valid entries
                  </p>
                </div>
                <CheckCircle className="h-12 w-12 text-green-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    API Success Rate
                  </p>
                  <p className="text-3xl font-bold text-purple-600 mt-2">
                    {stats.api_success_rate.toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {stats.api_sourced_prices} from API
                  </p>
                </div>
                <TrendingUp className="h-12 w-12 text-purple-600" />
              </div>
            </div>
          </div>
        )}

        {/* Pricing Cache Table */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">
                Pricing Cache
              </h2>
              <div className="flex items-center gap-4">
                <Filter className="h-5 w-5 text-gray-500" />
                <select
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1 text-sm"
                >
                  <option value="">All Providers</option>
                  <option value="aws">AWS</option>
                  <option value="azure">Azure</option>
                  <option value="gcp">GCP</option>
                </select>
                <select
                  value={regionFilter}
                  onChange={(e) => setRegionFilter(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1 text-sm"
                >
                  <option value="">All Regions</option>
                  <option value="us-east-1">US East 1</option>
                  <option value="us-west-2">US West 2</option>
                  <option value="eu-west-1">EU West 1</option>
                </select>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Provider
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Service
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Region
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Price
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Source
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Updated
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {cacheItems.map((item, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 uppercase">
                      {item.provider}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {item.service}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {item.region}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                      ${item.price_per_unit.toFixed(4)}/{item.unit}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {item.source === "api" ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          API
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                          Fallback
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatTimeSince(item.last_updated)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {item.is_expired ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                          Expired
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          Valid
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {cacheItems.length === 0 && (
            <div className="text-center py-12">
              <Database className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-500">No pricing data cached yet</p>
              <button
                onClick={handleRefreshPricing}
                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Refresh Pricing Data
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
