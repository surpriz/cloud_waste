"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Shield,
  Sparkles,
  Download,
  Trash2,
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Info
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface UserPreferences {
  id: string;
  user_id: string;
  ml_data_collection_consent: boolean;
  ml_consent_date: string | null;
  anonymized_industry: string | null;
  anonymized_company_size: string | null;
  email_scan_summaries: boolean;
  email_cost_alerts: boolean;
  email_marketing: boolean;
  data_retention_years: string;
  created_at: string;
  updated_at: string;
}

interface MLDataSummary {
  action_patterns: number;
  cost_trends: number;
  ml_training_data: number;
  lifecycle_events: number;
  metrics_history: number;
}

export default function PrivacySettingsPage() {
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [dataSummary, setDataSummary] = useState<MLDataSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [showError, setShowError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Fetch user preferences
      const prefsRes = await apiClient.get("/api/v1/preferences/me");
      setPreferences(prefsRes.data);

      // Fetch ML data summary
      const summaryRes = await apiClient.get("/api/v1/gdpr/my-data-summary");
      setDataSummary(summaryRes.data);
    } catch (error: any) {
      console.error("Failed to fetch privacy data:", error);
      setShowError(error.response?.data?.detail || "Failed to load privacy settings");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleMLConsent = async () => {
    if (!preferences) return;

    try {
      setSaving(true);

      const newConsentValue = !preferences.ml_data_collection_consent;

      const response = await apiClient.patch("/api/v1/preferences/me", {
        ml_data_collection_consent: newConsentValue,
      });

      setPreferences(response.data);
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
    } catch (error: any) {
      console.error("Failed to update ML consent:", error);
      setShowError(error.response?.data?.detail || "Failed to update consent");
      setTimeout(() => setShowError(null), 5000);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdatePreferences = async (updates: Partial<UserPreferences>) => {
    if (!preferences) return;

    try {
      setSaving(true);

      const response = await apiClient.patch("/api/v1/preferences/me", updates);

      setPreferences(response.data);
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
    } catch (error: any) {
      console.error("Failed to update preferences:", error);
      setShowError(error.response?.data?.detail || "Failed to update preferences");
      setTimeout(() => setShowError(null), 5000);
    } finally {
      setSaving(false);
    }
  };

  const handleExportData = async () => {
    try {
      const response = await apiClient.get("/api/v1/gdpr/export-my-data");

      // Download as JSON file
      const dataStr = JSON.stringify(response.data, null, 2);
      const dataBlob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(dataBlob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `cloudwaste-my-data-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
    } catch (error: any) {
      console.error("Failed to export data:", error);
      setShowError(error.response?.data?.detail || "Failed to export data");
      setTimeout(() => setShowError(null), 5000);
    }
  };

  const handleDeleteMLData = async () => {
    try {
      setDeleting(true);

      await apiClient.delete("/api/v1/gdpr/delete-my-ml-data");

      setShowDeleteConfirm(false);
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);

      // Refresh data
      await fetchData();
    } catch (error: any) {
      console.error("Failed to delete ML data:", error);
      setShowError(error.response?.data?.detail || "Failed to delete ML data");
      setTimeout(() => setShowError(null), 5000);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-300 dark:bg-gray-700 rounded w-1/3 mb-8"></div>
            <div className="space-y-4">
              <div className="h-64 bg-gray-300 dark:bg-gray-700 rounded"></div>
              <div className="h-64 bg-gray-300 dark:bg-gray-700 rounded"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/dashboard/settings"
            className="inline-flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Settings
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            Privacy & Data Collection
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Manage how CloudWaste collects and uses your data
          </p>
        </div>

        {/* Success/Error Messages */}
        {showSuccess && (
          <div className="mb-6 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
            <span className="text-green-800 dark:text-green-300">Changes saved successfully!</span>
          </div>
        )}

        {showError && (
          <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
            <span className="text-red-800 dark:text-red-300">{showError}</span>
          </div>
        )}

        {/* ML Data Collection Card */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-600" />
                ML Data Collection
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Help improve CloudWaste predictions by contributing anonymized data
              </p>
            </div>

            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={preferences?.ml_data_collection_consent || false}
                onChange={handleToggleMLConsent}
                disabled={saving}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {preferences?.ml_data_collection_consent && (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-4">
              <div className="flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
                <div>
                  <h3 className="font-semibold text-blue-900 dark:text-blue-300">
                    Early Access Perk
                  </h3>
                  <p className="text-sm text-blue-800 dark:text-blue-400 mt-1">
                    Contributors get early access to V2 AI prediction features
                  </p>
                  {preferences.ml_consent_date && (
                    <p className="text-xs text-blue-700 dark:text-blue-500 mt-2">
                      Consent given: {new Date(preferences.ml_consent_date).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* What Data is Collected */}
          <details className="mt-4 group">
            <summary className="cursor-pointer text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2 hover:text-gray-900 dark:hover:text-white">
              <Info className="w-4 h-4" />
              What data is collected?
            </summary>
            <div className="mt-3 ml-6 space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <p className="font-medium text-gray-900 dark:text-white">✅ Collected (anonymized):</p>
              <ul className="list-disc ml-5 space-y-1">
                <li>Resource types and patterns (e.g., "idle EBS volume")</li>
                <li>CloudWatch metrics trends (CPU, I/O, network)</li>
                <li>Your optimization decisions (delete/ignore/keep)</li>
                <li>Cost savings achieved</li>
              </ul>

              <p className="font-medium text-gray-900 dark:text-white mt-4">❌ NOT collected:</p>
              <ul className="list-disc ml-5 space-y-1">
                <li>AWS account IDs</li>
                <li>Resource names or IDs</li>
                <li>Tags with sensitive information</li>
                <li>Your company name</li>
              </ul>
            </div>
          </details>

          {/* Optional Context */}
          {preferences?.ml_data_collection_consent && (
            <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Optional: Help us improve recommendations (anonymized)
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-600 dark:text-gray-400 mb-2">
                    Industry
                  </label>
                  <select
                    value={preferences.anonymized_industry || ""}
                    onChange={(e) =>
                      handleUpdatePreferences({ anonymized_industry: e.target.value || null })
                    }
                    disabled={saving}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  >
                    <option value="">Not specified</option>
                    <option value="tech">Technology</option>
                    <option value="finance">Finance</option>
                    <option value="healthcare">Healthcare</option>
                    <option value="retail">Retail</option>
                    <option value="manufacturing">Manufacturing</option>
                    <option value="education">Education</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-gray-600 dark:text-gray-400 mb-2">
                    Company Size
                  </label>
                  <select
                    value={preferences.anonymized_company_size || ""}
                    onChange={(e) =>
                      handleUpdatePreferences({ anonymized_company_size: e.target.value || null })
                    }
                    disabled={saving}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                  >
                    <option value="">Not specified</option>
                    <option value="small">Small (&lt;50)</option>
                    <option value="medium">Medium (50-500)</option>
                    <option value="large">Large (500-5000)</option>
                    <option value="enterprise">Enterprise (5000+)</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Your Data Card */}
        {dataSummary && (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Your Data
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {dataSummary.action_patterns}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Action Patterns</div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {dataSummary.cost_trends}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Cost Trends</div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {preferences?.data_retention_years || "3"} years
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Retention Period</div>
              </div>
            </div>

            <div className="space-y-3">
              <button
                onClick={handleExportData}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                <Download className="w-4 h-4" />
                Export My Data (JSON)
              </button>

              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Delete My ML Data
              </button>
            </div>
          </div>
        )}

        {/* Data Retention */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Data Retention
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Choose how long we retain your ML data
          </p>

          <div className="flex gap-2">
            {["1", "2", "3"].map((years) => (
              <button
                key={years}
                onClick={() => handleUpdatePreferences({ data_retention_years: years })}
                disabled={saving}
                className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors ${
                  preferences?.data_retention_years === years
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                {years} {years === "1" ? "year" : "years"}
              </button>
            ))}
          </div>
        </div>

        {/* Delete Confirmation Modal */}
        {showDeleteConfirm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-md w-full">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                Delete ML Data?
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                This will permanently delete all ML data associated with your account. Fully anonymized data that cannot be linked back to you will be preserved for ML training.
              </p>

              <div className="flex gap-3">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleting}
                  className="flex-1 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteMLData}
                  disabled={deleting}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
