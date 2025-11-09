"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminAPI } from "@/lib/api";
import type { User, AdminStats, PricingStats, MLDataStats, MLExportResponse, SESMetrics, SESIdentityMetrics } from "@/types";
import { Shield, Users, UserCheck, UserX, Crown, Ban, CheckCircle, DollarSign, TrendingUp, Database, Download, Mail, AlertTriangle, CheckCircle2 } from "lucide-react";

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [pricingStats, setPricingStats] = useState<PricingStats | null>(null);
  const [mlStats, setMlStats] = useState<MLDataStats | null>(null);
  const [sesMetrics, setSesMetrics] = useState<SESMetrics | null>(null);
  const [sesIdentities, setSesIdentities] = useState<SESIdentityMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usersData, statsData, pricingData, mlData, sesData, sesIdentitiesData] = await Promise.all([
        adminAPI.listUsers(),
        adminAPI.getStats(),
        adminAPI.getPricingStats().catch(() => null), // Optional pricing stats
        adminAPI.getMLStats().catch(() => null), // Optional ML stats
        adminAPI.getSESMetrics().catch(() => null), // Optional SES metrics
        adminAPI.getSESIdentities().catch(() => []), // Optional SES identities
      ]);
      setUsers(usersData);
      setStats(statsData);
      setPricingStats(pricingData);
      setMlStats(mlData);
      setSesMetrics(sesData);
      setSesIdentities(sesIdentitiesData);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  };

  const handleExportMLData = async (days: number, format: string) => {
    try {
      setExportLoading(true);
      setExportSuccess(null);
      setError(null);
      const result = await adminAPI.exportMLData(days, format);
      setExportSuccess(result.message);
      await loadData(); // Refresh ML stats
      setTimeout(() => setExportSuccess(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to export ML data");
    } finally {
      setExportLoading(false);
    }
  };

  const handleToggleActive = async (userId: string) => {
    try {
      setActionLoading(userId);
      await adminAPI.toggleUserActive(userId);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to toggle user status");
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleSuperuser = async (user: User) => {
    if (
      !confirm(
        `Are you sure you want to ${
          user.is_superuser ? "demote" : "promote"
        } ${user.email} ${user.is_superuser ? "from" : "to"} admin?`
      )
    ) {
      return;
    }

    try {
      setActionLoading(user.id);
      await adminAPI.updateUser(user.id, { is_superuser: !user.is_superuser });
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to update user role");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (
      !confirm(
        `⚠️ WARNING: Are you sure you want to PERMANENTLY DELETE user ${user.email}?\n\nThis will delete:\n- User account\n- All cloud accounts\n- All scans\n- All orphan resources\n- All chat conversations\n\nThis action CANNOT be undone!`
      )
    ) {
      return;
    }

    try {
      setActionLoading(user.id);
      await adminAPI.deleteUser(user.id);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to delete user");
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Shield className="h-8 w-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900">Admin Panel</h1>
          </div>
          <p className="text-gray-600">
            Manage users, permissions, and view platform statistics
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
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
                    Total Users
                  </p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">
                    {stats.total_users}
                  </p>
                </div>
                <Users className="h-12 w-12 text-blue-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Active Users
                  </p>
                  <p className="text-3xl font-bold text-green-600 mt-2">
                    {stats.active_users}
                  </p>
                </div>
                <UserCheck className="h-12 w-12 text-green-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Blocked Users
                  </p>
                  <p className="text-3xl font-bold text-red-600 mt-2">
                    {stats.inactive_users}
                  </p>
                </div>
                <UserX className="h-12 w-12 text-red-600" />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">
                    Administrators
                  </p>
                  <p className="text-3xl font-bold text-purple-600 mt-2">
                    {stats.superusers}
                  </p>
                </div>
                <Crown className="h-12 w-12 text-purple-600" />
              </div>
            </div>
          </div>
        )}

        {/* Pricing System Status Widget */}
        {pricingStats && (
          <div className="mb-8 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg shadow-sm border border-green-200 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <DollarSign className="h-10 w-10 text-green-600" />
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    Dynamic Pricing System
                    {pricingStats.api_success_rate >= 80 ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        ✅ Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                        ⚠️ Degraded
                      </span>
                    )}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {pricingStats.total_cached_prices} prices cached | API Success: {pricingStats.api_success_rate.toFixed(1)}% |
                    Cache Hit: {pricingStats.cache_hit_rate.toFixed(1)}%
                  </p>
                </div>
              </div>
              <button
                onClick={() => router.push("/dashboard/admin/pricing")}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                <TrendingUp className="h-4 w-4" />
                View Details →
              </button>
            </div>
          </div>
        )}

        {/* ML Data Collection Widget */}
        {mlStats && (
          <div className="mb-8 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg shadow-sm border border-purple-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-4">
                <Database className="h-10 w-10 text-purple-600" />
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    ML Data Collection
                    {mlStats.total_ml_records > 0 ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        ✅ Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        📊 Waiting for data
                      </span>
                    )}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {mlStats.total_ml_records.toLocaleString()} total records | {mlStats.records_last_7_days.toLocaleString()} last 7 days | {mlStats.records_last_30_days.toLocaleString()} last 30 days
                  </p>
                </div>
              </div>
            </div>

            {/* Export Success Message */}
            {exportSuccess && (
              <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
                ✅ {exportSuccess}
              </div>
            )}

            {/* ML Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="bg-white rounded-lg p-4 border border-purple-100">
                <p className="text-sm text-gray-600">Total ML Records</p>
                <p className="text-2xl font-bold text-purple-600 mt-1">
                  {mlStats.total_ml_records.toLocaleString()}
                </p>
              </div>
              <div className="bg-white rounded-lg p-4 border border-purple-100">
                <p className="text-sm text-gray-600">User Actions Tracked</p>
                <p className="text-2xl font-bold text-purple-600 mt-1">
                  {mlStats.total_user_actions.toLocaleString()}
                </p>
              </div>
              <div className="bg-white rounded-lg p-4 border border-purple-100">
                <p className="text-sm text-gray-600">Cost Trends</p>
                <p className="text-2xl font-bold text-purple-600 mt-1">
                  {mlStats.total_cost_trends.toLocaleString()}
                </p>
              </div>
            </div>

            {/* Export Buttons */}
            <div className="flex gap-3">
              <button
                onClick={() => handleExportMLData(30, "json")}
                disabled={exportLoading}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="h-4 w-4" />
                {exportLoading ? "Exporting..." : "Export Last 30 Days (JSON)"}
              </button>
              <button
                onClick={() => handleExportMLData(90, "json")}
                disabled={exportLoading}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="h-4 w-4" />
                {exportLoading ? "Exporting..." : "Export Last 90 Days (JSON)"}
              </button>
              <button
                onClick={() => handleExportMLData(90, "csv")}
                disabled={exportLoading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="h-4 w-4" />
                {exportLoading ? "Exporting..." : "Export Last 90 Days (CSV)"}
              </button>
            </div>

            {mlStats.last_collection_date && (
              <p className="text-xs text-gray-500 mt-3">
                Last collection: {new Date(mlStats.last_collection_date).toLocaleString()}
              </p>
            )}
          </div>
        )}

        {/* AWS SES Email Monitoring Widget */}
        {sesMetrics && (
          <div className="mb-8 bg-gradient-to-r from-blue-50 to-cyan-50 rounded-lg shadow-sm border border-blue-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-4">
                <Mail className="h-10 w-10 text-blue-600" />
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    AWS SES Email Monitoring
                    {sesMetrics.reputation_status === "healthy" && sesMetrics.sending_enabled ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Healthy
                      </span>
                    ) : sesMetrics.reputation_status === "under_review" ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        Under Review
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        Probation
                      </span>
                    )}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Monitoring email deliverability and sender reputation in {sesMetrics.region}
                  </p>
                </div>
              </div>
              <button
                onClick={() => loadData()}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                Refresh
              </button>
            </div>

            {/* Critical Alerts */}
            {sesMetrics.has_critical_alerts && sesMetrics.alerts.length > 0 && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-red-900 mb-2">Critical Alerts</h4>
                    <ul className="text-sm text-red-700 space-y-1">
                      {sesMetrics.alerts.map((alert, index) => (
                        <li key={index}>• {alert}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Send Volume Stats */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Send Volume</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <p className="text-sm text-gray-600">Last 24 Hours</p>
                  <p className="text-2xl font-bold text-blue-600 mt-1">
                    {sesMetrics.emails_sent_24h.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">emails sent</p>
                </div>
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <p className="text-sm text-gray-600">Last 7 Days</p>
                  <p className="text-2xl font-bold text-blue-600 mt-1">
                    {sesMetrics.emails_sent_7d.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">emails sent</p>
                </div>
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <p className="text-sm text-gray-600">Last 30 Days</p>
                  <p className="text-2xl font-bold text-blue-600 mt-1">
                    {sesMetrics.emails_sent_30d.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">emails sent</p>
                </div>
              </div>
            </div>

            {/* Deliverability Metrics */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Deliverability Metrics</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className={`bg-white rounded-lg p-4 border-2 ${
                  sesMetrics.delivery_rate >= 95 ? 'border-green-200' :
                  sesMetrics.delivery_rate >= 90 ? 'border-orange-200' : 'border-red-200'
                }`}>
                  <p className="text-sm text-gray-600">Delivery Rate</p>
                  <p className={`text-3xl font-bold mt-1 ${
                    sesMetrics.delivery_rate >= 95 ? 'text-green-600' :
                    sesMetrics.delivery_rate >= 90 ? 'text-orange-600' : 'text-red-600'
                  }`}>
                    {sesMetrics.delivery_rate.toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {sesMetrics.delivery_rate >= 95 ? '✅ Excellent' :
                     sesMetrics.delivery_rate >= 90 ? '⚠️ Fair' : '❌ Poor'}
                  </p>
                </div>
                <div className={`bg-white rounded-lg p-4 border-2 ${
                  sesMetrics.bounce_rate <= 5 ? 'border-green-200' :
                  sesMetrics.bounce_rate <= 10 ? 'border-orange-200' : 'border-red-200'
                }`}>
                  <p className="text-sm text-gray-600">Bounce Rate</p>
                  <p className={`text-3xl font-bold mt-1 ${
                    sesMetrics.bounce_rate <= 5 ? 'text-green-600' :
                    sesMetrics.bounce_rate <= 10 ? 'text-orange-600' : 'text-red-600'
                  }`}>
                    {sesMetrics.bounce_rate.toFixed(2)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Hard: {sesMetrics.hard_bounce_rate.toFixed(2)}% | Soft: {sesMetrics.soft_bounce_rate.toFixed(2)}%
                  </p>
                </div>
                <div className={`bg-white rounded-lg p-4 border-2 ${
                  sesMetrics.complaint_rate <= 0.3 ? 'border-green-200' :
                  sesMetrics.complaint_rate <= 0.5 ? 'border-orange-200' : 'border-red-200'
                }`}>
                  <p className="text-sm text-gray-600">Complaint Rate</p>
                  <p className={`text-3xl font-bold mt-1 ${
                    sesMetrics.complaint_rate <= 0.3 ? 'text-green-600' :
                    sesMetrics.complaint_rate <= 0.5 ? 'text-orange-600' : 'text-red-600'
                  }`}>
                    {sesMetrics.complaint_rate.toFixed(3)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {sesMetrics.complaint_rate <= 0.3 ? '✅ Safe' :
                     sesMetrics.complaint_rate <= 0.5 ? '⚠️ Warning' : '❌ Critical'}
                  </p>
                </div>
              </div>
            </div>

            {/* Quotas and Limits */}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Send Quotas & Limits</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <p className="text-sm text-gray-600">Max Send Rate</p>
                  <p className="text-2xl font-bold text-blue-600 mt-1">
                    {sesMetrics.max_send_rate.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">emails/second</p>
                </div>
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <p className="text-sm text-gray-600">Daily Quota</p>
                  <p className="text-2xl font-bold text-blue-600 mt-1">
                    {sesMetrics.daily_quota.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">emails/day</p>
                </div>
                <div className={`bg-white rounded-lg p-4 border-2 ${
                  sesMetrics.quota_usage_percentage < 80 ? 'border-green-200' :
                  sesMetrics.quota_usage_percentage < 95 ? 'border-orange-200' : 'border-red-200'
                }`}>
                  <p className="text-sm text-gray-600">Quota Usage</p>
                  <p className={`text-2xl font-bold mt-1 ${
                    sesMetrics.quota_usage_percentage < 80 ? 'text-green-600' :
                    sesMetrics.quota_usage_percentage < 95 ? 'text-orange-600' : 'text-red-600'
                  }`}>
                    {sesMetrics.quota_usage_percentage.toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {sesMetrics.daily_sent.toLocaleString()} / {sesMetrics.daily_quota.toLocaleString()} sent today
                  </p>
                </div>
              </div>
            </div>

            {/* Identity Breakdown Table */}
            {sesIdentities.length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Identity Breakdown</h4>
                <div className="bg-white rounded-lg border border-blue-100 overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-blue-50 border-b border-blue-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">Domain</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">Type</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-600 uppercase">DKIM</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">24h</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">7d</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">30d</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">Bounce</th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-600 uppercase">Complaint</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {sesIdentities.map((identity, index) => (
                        <tr key={index} className="hover:bg-blue-50/30">
                          <td className="px-4 py-3">
                            <span className="text-sm font-medium text-gray-900">{identity.identity}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-sm text-gray-600">{identity.identity_type}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              identity.verification_status === "Success" || identity.verification_status === "SUCCESS"
                                ? "bg-green-100 text-green-800"
                                : identity.verification_status === "Pending"
                                ? "bg-orange-100 text-orange-800"
                                : "bg-red-100 text-red-800"
                            }`}>
                              {identity.verification_status === "Success" || identity.verification_status === "SUCCESS" ? "✓ Verified" : identity.verification_status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              identity.dkim_enabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"
                            }`}>
                              {identity.dkim_enabled ? "✓ Enabled" : "Disabled"}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="text-sm font-medium text-blue-600">
                              {identity.emails_sent_24h.toLocaleString()}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="text-sm font-medium text-blue-600">
                              {identity.emails_sent_7d.toLocaleString()}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className="text-sm font-medium text-blue-600">
                              {identity.emails_sent_30d.toLocaleString()}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className={`text-sm font-semibold ${
                              identity.bounce_rate === 0 ? "text-gray-400" :
                              identity.bounce_rate <= 2 ? "text-green-600" :
                              identity.bounce_rate <= 5 ? "text-orange-600" : "text-red-600"
                            }`}>
                              {identity.bounce_rate.toFixed(2)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span className={`text-sm font-semibold ${
                              identity.complaint_rate === 0 ? "text-gray-400" :
                              identity.complaint_rate <= 0.1 ? "text-green-600" :
                              identity.complaint_rate <= 0.3 ? "text-orange-600" : "text-red-600"
                            }`}>
                              {identity.complaint_rate.toFixed(3)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Note: Per-identity metrics require CloudWatch Logs or Configuration Sets. Values may show 0 without proper setup.
                </p>
              </div>
            )}

            {/* Footer Info */}
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-blue-200">
              <div className="flex items-center gap-4 text-xs text-gray-600">
                <span>
                  Sending: {sesMetrics.sending_enabled ?
                    <span className="text-green-600 font-medium">✓ Enabled</span> :
                    <span className="text-red-600 font-medium">✗ Disabled</span>
                  }
                </span>
                <span>•</span>
                <span>Suppression List: {sesMetrics.suppression_list_size.toLocaleString()} addresses</span>
              </div>
              <p className="text-xs text-gray-500">
                Last updated: {new Date(sesMetrics.last_updated).toLocaleString()}
              </p>
            </div>
          </div>
        )}

        {/* Users Table */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">All Users</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created At
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {user.full_name || "N/A"}
                        </div>
                        <div className="text-sm text-gray-500">
                          {user.email}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(user.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col gap-2">
                        {user.is_active ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            <Ban className="h-3 w-3 mr-1" />
                            Blocked
                          </span>
                        )}
                        {user.email_verified ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            ✉️ Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                            ⏱️ Pending
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {user.is_superuser ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                          <Crown className="h-3 w-3 mr-1" />
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          Client
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                      <button
                        onClick={() => handleToggleActive(user.id)}
                        disabled={actionLoading === user.id}
                        className={`${
                          user.is_active
                            ? "text-red-600 hover:text-red-900"
                            : "text-green-600 hover:text-green-900"
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                      >
                        {actionLoading === user.id ? (
                          "Loading..."
                        ) : user.is_active ? (
                          "Block"
                        ) : (
                          "Unblock"
                        )}
                      </button>
                      <span className="text-gray-300">|</span>
                      <button
                        onClick={() => handleToggleSuperuser(user)}
                        disabled={actionLoading === user.id}
                        className="text-purple-600 hover:text-purple-900 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {actionLoading === user.id
                          ? "Loading..."
                          : user.is_superuser
                          ? "Demote"
                          : "Promote"}
                      </button>
                      <span className="text-gray-300">|</span>
                      <button
                        onClick={() => handleDeleteUser(user)}
                        disabled={actionLoading === user.id}
                        className="text-red-600 hover:text-red-900 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {actionLoading === user.id ? "Loading..." : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {users.length === 0 && (
            <div className="text-center py-12">
              <Users className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-500">No users found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
