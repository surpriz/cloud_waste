"use client";

import { useState, useEffect } from "react";
import { Search, Check, Loader2, AlertCircle, ArrowRight } from "lucide-react";
import { useAccountStore } from "@/stores/useAccountStore";
import { useScanStore } from "@/stores/useScanStore";
import Link from "next/link";

interface RunScanStepProps {
  onNext: () => void;
  onBack: () => void;
}

/**
 * Run Scan Step - Third onboarding step
 *
 * Guides user to run their first scan or shows scan in progress
 */
export function RunScanStep({ onNext, onBack }: RunScanStepProps) {
  const { accounts } = useAccountStore();
  const { scans, summary } = useScanStore();
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);

  const hasAccounts = accounts.length > 0;
  const hasCompletedScans = summary?.completed_scans && summary.completed_scans > 0;
  const recentScans = scans.filter(
    (scan) => scan.status === "completed" || scan.status === "running"
  );

  // Simulate scan progress (in real app, this would come from API polling)
  useEffect(() => {
    if (isScanning && scanProgress < 100) {
      const timer = setTimeout(() => {
        setScanProgress((prev) => Math.min(prev + 10, 100));
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [isScanning, scanProgress]);

  const handleStartScan = () => {
    setIsScanning(true);
    setScanProgress(0);
    // TODO: Trigger actual scan API call
  };

  return (
    <div className="text-center max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div
          className={`inline-flex items-center justify-center h-16 w-16 rounded-2xl shadow-lg mb-4 ${
            isScanning
              ? "bg-gradient-to-br from-green-600 to-emerald-600 animate-pulse"
              : "bg-gradient-to-br from-purple-600 to-pink-600"
          }`}
        >
          {isScanning ? (
            <Loader2 className="h-8 w-8 text-white animate-spin" />
          ) : (
            <Search className="h-8 w-8 text-white" />
          )}
        </div>

        <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mb-3">
          {hasCompletedScans
            ? "Scan Complete!"
            : isScanning
            ? "Scanning Your Cloud..."
            : "Run Your First Scan"}
        </h2>

        <p className="text-lg text-gray-600">
          {hasCompletedScans
            ? "We've analyzed your cloud infrastructure"
            : isScanning
            ? "Analyzing your cloud resources for waste"
            : "Detect orphaned resources and wasteful spending"}
        </p>
      </div>

      {/* No accounts warning */}
      {!hasAccounts && (
        <div className="mb-8 rounded-2xl border-2 border-orange-300 bg-orange-50 p-6">
          <div className="flex items-center justify-center gap-3 mb-3">
            <AlertCircle className="h-6 w-6 text-orange-600" />
            <h3 className="text-xl font-bold text-orange-900">
              No Cloud Accounts Connected
            </h3>
          </div>

          <p className="text-orange-700 mb-4">
            You need to connect at least one cloud account before running a scan.
          </p>

          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 rounded-xl bg-orange-600 px-6 py-3 font-semibold text-white hover:bg-orange-700 transition-colors"
          >
            Go Back to Add Account
          </button>
        </div>
      )}

      {/* Scan completed */}
      {hasCompletedScans && (
        <div className="mb-8 rounded-2xl border-2 border-green-300 bg-green-50 p-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-600">
              <Check className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-green-900">
              First Scan Completed!
            </h3>
          </div>

          <div className="grid gap-4 md:grid-cols-3 mb-6 text-left">
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <p className="text-sm text-gray-600 mb-1">Resources Scanned</p>
              <p className="text-2xl font-bold text-gray-900">
                {summary?.total_scans || 0}
              </p>
            </div>

            <div className="rounded-xl bg-white p-4 shadow-sm">
              <p className="text-sm text-gray-600 mb-1">Orphans Found</p>
              <p className="text-2xl font-bold text-orange-600">
                {recentScans[0]?.orphan_resources_found || 0}
              </p>
            </div>

            <div className="rounded-xl bg-white p-4 shadow-sm">
              <p className="text-sm text-gray-600 mb-1">Potential Savings</p>
              <p className="text-2xl font-bold text-green-600">
                ${recentScans[0]?.estimated_monthly_waste?.toFixed(2) || "0.00"}
                /mo
              </p>
            </div>
          </div>

          <button
            onClick={onNext}
            className="inline-flex items-center gap-2 rounded-xl bg-green-600 px-8 py-4 text-lg font-semibold text-white hover:bg-green-700 transition-colors shadow-lg"
          >
            Review Your Results
            <ArrowRight className="h-5 w-5" />
          </button>
        </div>
      )}

      {/* Scan in progress */}
      {isScanning && !hasCompletedScans && (
        <div className="mb-8 rounded-2xl border-2 border-purple-300 bg-purple-50 p-8">
          <div className="mb-6">
            <div className="relative h-4 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="absolute h-full bg-gradient-to-r from-purple-600 to-pink-600 rounded-full transition-all duration-1000 ease-out"
                style={{ width: `${scanProgress}%` }}
              ></div>
            </div>
            <p className="mt-3 text-sm text-gray-600">
              {scanProgress}% Complete • Scanning resources...
            </p>
          </div>

          <div className="space-y-2 text-left max-w-md mx-auto">
            {[
              { text: "Connecting to cloud provider", done: scanProgress > 20 },
              { text: "Scanning EC2 instances", done: scanProgress > 40 },
              { text: "Analyzing EBS volumes", done: scanProgress > 60 },
              { text: "Checking load balancers", done: scanProgress > 80 },
              { text: "Calculating cost savings", done: scanProgress === 100 },
            ].map((step, index) => (
              <div key={index} className="flex items-center gap-3">
                {step.done ? (
                  <Check className="h-5 w-5 text-green-600 flex-shrink-0" />
                ) : (
                  <Loader2 className="h-5 w-5 text-purple-600 animate-spin flex-shrink-0" />
                )}
                <span
                  className={`text-sm ${
                    step.done ? "text-green-700 font-medium" : "text-gray-600"
                  }`}
                >
                  {step.text}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ready to scan */}
      {hasAccounts && !hasCompletedScans && !isScanning && (
        <>
          <div className="mb-8 rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              What We'll Scan
            </h3>

            <div className="grid gap-3 md:grid-cols-2 text-left mb-6">
              {[
                "Unattached EBS volumes",
                "Orphaned EBS snapshots",
                "Unassociated Elastic IPs",
                "Stopped EC2 instances (>30 days)",
                "Idle load balancers",
                "Unused RDS instances",
                "Empty S3 buckets",
                "And 18+ more resource types",
              ].map((item, index) => (
                <div key={index} className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-700">{item}</span>
                </div>
              ))}
            </div>

            <p className="text-sm text-gray-600 mb-6">
              Connected accounts: <strong>{accounts.length}</strong> •
              Estimated scan time: <strong>2-5 minutes</strong>
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button
                onClick={handleStartScan}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 px-8 py-4 text-lg font-semibold text-white shadow-lg hover:shadow-2xl transition-all hover:scale-105"
              >
                <Search className="h-5 w-5" />
                Start Scanning Now
              </button>

              <Link
                href="/dashboard/scans"
                className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Go to Scans Page
              </Link>
            </div>
          </div>

          <p className="text-sm text-gray-500">
            💡 Scans are read-only and safe - we never modify your cloud resources
          </p>
        </>
      )}
    </div>
  );
}
