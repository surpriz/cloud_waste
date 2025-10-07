"use client";

import { useEffect, useState } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { useScanStore } from "@/stores/useScanStore";
import {
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  DollarSign,
  AlertTriangle,
  Trash2,
  Info,
} from "lucide-react";

export default function ScansPage() {
  const { accounts, fetchAccounts } = useAccountStore();
  const { scans, fetchScans, createScan, deleteAllScans, summary, fetchSummary, isLoading } =
    useScanStore();
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [isDeletingAll, setIsDeletingAll] = useState(false);

  useEffect(() => {
    fetchAccounts();
    fetchScans();
    fetchSummary();
  }, [fetchAccounts, fetchScans, fetchSummary]);

  // Auto-refresh scans if there are any in progress or pending
  useEffect(() => {
    const hasActiveScan = scans.some(
      (scan) => scan.status === "in_progress" || scan.status === "pending"
    );

    if (!hasActiveScan) return;

    // Poll every 3 seconds while scans are active
    const interval = setInterval(() => {
      fetchScans();
      fetchSummary();
    }, 3000);

    return () => clearInterval(interval);
  }, [scans, fetchScans, fetchSummary]);

  const handleStartScan = async () => {
    if (!selectedAccountId) {
      alert("Please select an account");
      return;
    }

    try {
      await createScan({
        cloud_account_id: selectedAccountId,
        scan_type: "manual",
      });
      // Refresh scans list
      setTimeout(() => fetchScans(), 1000);
    } catch (err) {
      // Error handled by store
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm("Êtes-vous sûr de vouloir supprimer tous les scans ? Cette action est irréversible.")) {
      return;
    }

    setIsDeletingAll(true);
    try {
      await deleteAllScans();
      await fetchSummary();
    } catch (err) {
      console.error("Failed to delete all scans:", err);
    } finally {
      setIsDeletingAll(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Scans</h1>
        <p className="mt-2 text-gray-600">
          Manage and monitor your cloud resource scans
        </p>
      </div>

      {/* Summary Stats */}
      {summary && (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Scans"
            value={summary.total_scans}
            icon={RefreshCw}
            color="blue"
          />
          <StatCard
            title="Completed"
            value={summary.completed_scans}
            icon={CheckCircle}
            color="green"
          />
          <StatCard
            title="Failed"
            value={summary.failed_scans}
            icon={XCircle}
            color="red"
          />
          <StatCard
            title="Monthly Waste"
            value={`$${summary.total_monthly_waste.toFixed(2)}`}
            icon={DollarSign}
            color="orange"
          />
        </div>
      )}

      {/* Start New Scan */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold text-gray-900">Start New Scan</h2>
        <div className="mt-4 flex gap-4">
          <select
            value={selectedAccountId}
            onChange={(e) => setSelectedAccountId(e.target.value)}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2"
          >
            <option value="">Select a cloud account</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.account_name} ({account.provider.toUpperCase()})
              </option>
            ))}
          </select>
          <button
            onClick={handleStartScan}
            disabled={!selectedAccountId || isLoading}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2 font-medium text-white hover:bg-blue-700 disabled:bg-blue-300"
          >
            <Play className="h-5 w-5" />
            Start Scan
          </button>
        </div>
      </div>

      {/* Scans List */}
      <div className="rounded-lg border bg-white shadow-sm">
        <div className="border-b p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">Recent Scans</h2>
            {scans.length > 0 && (
              <button
                onClick={handleDeleteAll}
                disabled={isDeletingAll}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:bg-red-300 transition-colors"
                title="Supprimer tous les scans"
              >
                <Trash2 className={`h-4 w-4 ${isDeletingAll ? "animate-spin" : ""}`} />
                Supprimer tous les scans
              </button>
            )}
          </div>
        </div>
        <div className="divide-y">
          {scans.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              No scans yet. Start your first scan to detect orphaned resources.
            </div>
          ) : (
            scans.map((scan) => <ScanRow key={scan.id} scan={scan} />)
          )}
        </div>
      </div>
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

function ScanRow({ scan }: any) {
  const { accounts } = useAccountStore();
  const { deleteScan, fetchScans } = useScanStore();
  const [isDeleting, setIsDeleting] = useState(false);
  const account = accounts.find((a) => a.id === scan.cloud_account_id);

  const statusConfig: any = {
    pending: {
      icon: Clock,
      color: "text-gray-600",
      bg: "bg-gray-100",
      label: "Pending",
    },
    in_progress: {
      icon: Loader2,
      color: "text-blue-600",
      bg: "bg-blue-100",
      label: "In Progress",
      spin: true,
    },
    completed: {
      icon: CheckCircle,
      color: "text-green-600",
      bg: "bg-green-100",
      label: "Completed",
    },
    failed: {
      icon: XCircle,
      color: "text-red-600",
      bg: "bg-red-100",
      label: "Failed",
    },
  };

  const config = statusConfig[scan.status] || statusConfig.pending;
  const StatusIcon = config.icon;

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this scan?")) return;

    setIsDeleting(true);
    try {
      await deleteScan(scan.id);
      await fetchScans();
    } catch (err) {
      console.error("Failed to delete scan:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="p-6 hover:bg-gray-50">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <div className={`rounded-lg p-2 ${config.bg}`}>
              <StatusIcon
                className={`h-5 w-5 ${config.color} ${
                  config.spin ? "animate-spin" : ""
                }`}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">
                {account?.account_name || "Unknown Account"}
              </h3>
              <p className="text-sm text-gray-600">
                {scan.scan_type === "manual" ? "Manual Scan" : "Scheduled Scan"}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-8 text-sm">
          <div className="text-center">
            <p className="font-semibold text-gray-900">
              {scan.orphan_resources_found}
            </p>
            <p className="text-gray-500">Resources</p>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900">
              ${scan.estimated_monthly_waste.toFixed(2)}
            </p>
            <p className="text-gray-500">Est. Waste</p>
          </div>
          <div className="text-center">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${config.bg} ${config.color}`}
            >
              {config.label}
            </span>
          </div>
          <div className="w-32 text-right text-gray-500">
            {scan.completed_at
              ? new Date(scan.completed_at).toLocaleString()
              : new Date(scan.created_at).toLocaleString()}
          </div>
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600 transition-colors disabled:opacity-50"
            title="Delete scan"
          >
            <Trash2 className={`h-5 w-5 ${isDeleting ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Success message - No orphans found */}
      {scan.status === "completed" && scan.orphan_resources_found === 0 && (
        <div className="mt-4 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            <span className="font-semibold">
              ✨ Great news! No orphaned resources found.
            </span>
          </div>
          <p className="ml-6 mt-1 text-green-600">
            Your cloud infrastructure is clean and optimized.
          </p>
        </div>
      )}

      {/* Warning message - Orphans found */}
      {scan.status === "completed" && scan.orphan_resources_found > 0 && (
        <div className="mt-4 rounded-lg bg-orange-50 border border-orange-200 p-3 text-sm text-orange-700">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            <span className="font-semibold">
              ⚠️ Found {scan.orphan_resources_found} orphaned resource
              {scan.orphan_resources_found > 1 ? "s" : ""}.
            </span>
          </div>
          <p className="ml-6 mt-1 text-orange-600">
            Future savings: ${scan.estimated_monthly_waste.toFixed(2)}/month
            (${(scan.estimated_monthly_waste * 12).toFixed(2)}/year) if cleaned up now
          </p>
        </div>
      )}

      {/* Error message */}
      {scan.error_message && (
        <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-600">
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4" />
            <span className="font-semibold">Scan failed</span>
          </div>
          <p className="ml-6 mt-1">{scan.error_message}</p>
        </div>
      )}
    </div>
  );
}
