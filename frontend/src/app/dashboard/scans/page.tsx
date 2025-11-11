"use client";

import { useEffect, useState } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { useScanStore } from "@/stores/useScanStore";
import { ScanProgressModal } from "@/components/dashboard/ScanProgressModal";
import { scansAPI } from "@/lib/api";
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
  CheckSquare,
  Square,
  Zap,
} from "lucide-react";

export default function ScansPage() {
  const { accounts, fetchAccounts } = useAccountStore();
  const { scans, fetchScans, createScan, deleteAllScans, summary, fetchSummary, isLoading } =
    useScanStore();
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [isDeletingAll, setIsDeletingAll] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [activeScanId, setActiveScanId] = useState<string | null>(null);
  const [showProgressModal, setShowProgressModal] = useState(false);

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

  // Auto-open progress modal when a new scan starts
  useEffect(() => {
    const inProgressScan = scans.find((scan) => scan.status === "in_progress");
    if (inProgressScan && !activeScanId) {
      setActiveScanId(inProgressScan.id);
      setShowProgressModal(true);
    }
  }, [scans, activeScanId]);

  // Get account name for active scan
  const getActiveScanAccountName = () => {
    if (!activeScanId) return "Unknown Account";
    const scan = scans.find((s) => s.id === activeScanId);
    if (!scan) return "Unknown Account";
    const account = accounts.find((a) => a.id === scan.cloud_account_id);
    return account?.account_name || "Unknown Account";
  };

  // Handle progress modal completion
  const handleProgressComplete = () => {
    fetchScans();
    fetchSummary();
    setActiveScanId(null);
  };

  // Handle progress modal close
  const handleProgressClose = () => {
    setShowProgressModal(false);
    // Keep activeScanId so we don't reopen the modal
  };

  const toggleAccountSelection = (accountId: string) => {
    setSelectedAccountIds((prev) =>
      prev.includes(accountId)
        ? prev.filter((id) => id !== accountId)
        : [...prev, accountId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedAccountIds.length === accounts.length) {
      setSelectedAccountIds([]);
    } else {
      setSelectedAccountIds(accounts.map((acc) => acc.id));
    }
  };

  const handleScanSelected = async () => {
    if (selectedAccountIds.length === 0) {
      alert("Please select at least one account");
      return;
    }

    setIsScanning(true);
    try {
      // Launch scans for all selected accounts
      const scanPromises = selectedAccountIds.map((accountId) =>
        createScan({
          cloud_account_id: accountId,
          scan_type: "manual",
        })
      );
      await Promise.all(scanPromises);

      // Clear selection
      setSelectedAccountIds([]);

      // Refresh scans list
      setTimeout(() => fetchScans(), 1000);
    } catch (err) {
      console.error("Failed to start scans:", err);
    } finally {
      setIsScanning(false);
    }
  };

  const handleScanAll = async () => {
    if (accounts.length === 0) {
      alert("No accounts available to scan");
      return;
    }

    if (!confirm(`Start scanning all ${accounts.length} accounts?`)) {
      return;
    }

    setIsScanning(true);
    try {
      const scanPromises = accounts.map((account) =>
        createScan({
          cloud_account_id: account.id,
          scan_type: "manual",
        })
      );
      await Promise.all(scanPromises);

      // Refresh scans list
      setTimeout(() => fetchScans(), 1000);
    } catch (err) {
      console.error("Failed to start all scans:", err);
    } finally {
      setIsScanning(false);
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
    <div className="space-y-4 md:space-y-6">
      {/* Progress Modal */}
      {activeScanId && (
        <ScanProgressModal
          scanId={activeScanId}
          accountName={getActiveScanAccountName()}
          isOpen={showProgressModal}
          onClose={handleProgressClose}
          onComplete={handleProgressComplete}
        />
      )}

      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Scans</h1>
        <p className="mt-1 md:mt-2 text-sm md:text-base text-gray-600">
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
      <div className="rounded-lg border bg-white shadow-sm">
        <div className="border-b p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">Start New Scan</h2>
              <p className="mt-1 text-sm text-gray-600">
                Select accounts to scan for orphaned resources
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={toggleSelectAll}
                disabled={accounts.length === 0 || isScanning}
                className="flex items-center gap-2 rounded-lg border-2 border-blue-600 bg-white px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 disabled:border-blue-300 disabled:text-blue-300 transition-colors"
              >
                {selectedAccountIds.length === accounts.length ? (
                  <>
                    <CheckSquare className="h-4 w-4" />
                    Deselect All
                  </>
                ) : (
                  <>
                    <Square className="h-4 w-4" />
                    Select All
                  </>
                )}
              </button>
              <button
                onClick={handleScanAll}
                disabled={accounts.length === 0 || isScanning}
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-2 font-medium text-white hover:from-purple-700 hover:to-blue-700 disabled:from-purple-300 disabled:to-blue-300 transition-all shadow-md"
              >
                {isScanning ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Scanning...
                  </>
                ) : (
                  <>
                    <Zap className="h-5 w-5" />
                    Scan All ({accounts.length})
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {accounts.length === 0 ? (
          <div className="p-12 text-center">
            <Info className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-600">
              No cloud accounts configured yet.
            </p>
            <p className="mt-2 text-sm text-gray-500">
              Add a cloud account to start scanning for orphaned resources.
            </p>
          </div>
        ) : (
          <>
            <div className="p-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {accounts.map((account) => (
                <div
                  key={account.id}
                  onClick={() => toggleAccountSelection(account.id)}
                  className={`cursor-pointer rounded-lg border-2 p-4 transition-all hover:shadow-md ${
                    selectedAccountIds.includes(account.id)
                      ? "border-blue-600 bg-blue-50"
                      : "border-gray-200 bg-white hover:border-blue-300"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 pt-0.5">
                      {selectedAccountIds.includes(account.id) ? (
                        <CheckSquare className="h-5 w-5 text-blue-600" />
                      ) : (
                        <Square className="h-5 w-5 text-gray-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900 truncate">
                        {account.account_name}
                      </h3>
                      <p className="mt-1 text-sm text-gray-600">
                        {account.provider.toUpperCase()}
                      </p>
                      {account.last_scan_at && (
                        <p className="mt-1 text-xs text-gray-500">
                          Last scan:{" "}
                          {new Date(account.last_scan_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="border-t p-6 bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  {selectedAccountIds.length > 0 ? (
                    <span className="font-semibold">
                      {selectedAccountIds.length} account
                      {selectedAccountIds.length > 1 ? "s" : ""} selected
                    </span>
                  ) : (
                    <span>No accounts selected</span>
                  )}
                </div>
                <button
                  onClick={handleScanSelected}
                  disabled={selectedAccountIds.length === 0 || isScanning}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white hover:bg-blue-700 disabled:bg-blue-300 transition-colors shadow-md"
                >
                  {isScanning ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Scanning...
                    </>
                  ) : (
                    <>
                      <Play className="h-5 w-5" />
                      Scan Selected ({selectedAccountIds.length})
                    </>
                  )}
                </button>
              </div>
            </div>
          </>
        )}
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
            scans.map((scan) => (
              <ScanRow
                key={scan.id}
                scan={scan}
                onViewProgress={(scanId: string) => {
                  setActiveScanId(scanId);
                  setShowProgressModal(true);
                }}
              />
            ))
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

function ScanRow({ scan, onViewProgress }: any) {
  const { accounts } = useAccountStore();
  const { deleteScan, fetchScans } = useScanStore();
  const [isDeleting, setIsDeleting] = useState(false);
  const [progress, setProgress] = useState<any>(null);
  const account = accounts.find((a) => a.id === scan.cloud_account_id);

  // Fetch progress for in_progress scans
  useEffect(() => {
    if (scan.status === "in_progress") {
      const fetchProgress = async () => {
        try {
          const data = await scansAPI.getProgress(scan.id);
          setProgress(data);
        } catch (err) {
          console.error("Failed to fetch progress:", err);
        }
      };

      fetchProgress();
      const interval = setInterval(fetchProgress, 3000);
      return () => clearInterval(interval);
    }
  }, [scan.status, scan.id]);

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
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900">
                {account?.account_name || "Unknown Account"}
              </h3>
              <p className="text-sm text-gray-600">
                {scan.scan_type === "manual" ? "Manual Scan" : "Scheduled Scan"}
              </p>

              {/* Mini Progress Bar for in_progress scans */}
              {scan.status === "in_progress" && progress && (
                <div className="mt-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-blue-600 font-medium">
                      {progress.current_step}
                    </span>
                    <span className="text-xs font-semibold text-blue-900">
                      {progress.percent}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500"
                      style={{ width: `${progress.percent}%` }}
                    />
                  </div>
                </div>
              )}
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

          {/* View Progress Button for in_progress scans */}
          {scan.status === "in_progress" && (
            <button
              onClick={() => onViewProgress && onViewProgress(scan.id)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 transition-colors"
              title="View detailed progress"
            >
              View Progress
            </button>
          )}

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
