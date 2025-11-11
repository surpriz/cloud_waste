"use client";

import { useEffect, useState } from "react";
import { Cloud, AlertCircle, CheckCircle, Loader2, Clock, Database } from "lucide-react";
import type { ScanProgress } from "@/types";

interface ScanProgressCardProps {
  progress: ScanProgress;
  accountName: string;
}

/**
 * ScanProgressCard Component
 *
 * Displays real-time progress of a cloud scan with detailed information:
 * - Progress bar (0-100%)
 * - Current region being scanned
 * - Resources found so far
 * - Elapsed time
 * - Current step description
 */
export function ScanProgressCard({ progress, accountName }: ScanProgressCardProps) {
  const [displayPercent, setDisplayPercent] = useState(0);

  // Animate progress bar
  useEffect(() => {
    const timer = setTimeout(() => {
      setDisplayPercent(progress.percent);
    }, 100);
    return () => clearTimeout(timer);
  }, [progress.percent]);

  // Format elapsed time (e.g., "1m 27s")
  const formatElapsed = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  // Get status icon and color based on state
  const getStatusIcon = () => {
    switch (progress.state) {
      case "PENDING":
        return <Clock className="h-8 w-8 text-gray-400 animate-pulse" />;
      case "PROGRESS":
        return <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />;
      case "SUCCESS":
        return <CheckCircle className="h-8 w-8 text-green-600" />;
      case "FAILURE":
        return <AlertCircle className="h-8 w-8 text-red-600" />;
      default:
        return <Cloud className="h-8 w-8 text-gray-400" />;
    }
  };

  const getStatusColor = () => {
    switch (progress.state) {
      case "PENDING":
        return "text-gray-600";
      case "PROGRESS":
        return "text-blue-600";
      case "SUCCESS":
        return "text-green-600";
      case "FAILURE":
        return "text-red-600";
      default:
        return "text-gray-600";
    }
  };

  const getProgressBarColor = () => {
    switch (progress.state) {
      case "SUCCESS":
        return "from-green-500 to-emerald-600";
      case "FAILURE":
        return "from-red-500 to-red-600";
      default:
        return "from-blue-600 to-purple-600";
    }
  };

  return (
    <div className="rounded-2xl border-2 border-gray-200 bg-white p-8 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          {getStatusIcon()}
          <div>
            <h3 className="text-2xl font-bold text-gray-900">{accountName}</h3>
            <p className={`text-sm font-medium ${getStatusColor()}`}>
              {progress.current_step || "Processing..."}
            </p>
          </div>
        </div>
        {progress.state === "PROGRESS" && (
          <div className="flex items-center gap-2 text-gray-600">
            <Clock className="h-5 w-5" />
            <span className="font-mono text-lg font-semibold">
              {formatElapsed(progress.elapsed_seconds)}
            </span>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            Step {progress.current} of {progress.total}
          </span>
          <span className="text-2xl font-bold text-gray-900">
            {displayPercent}%
          </span>
        </div>
        <div className="relative h-4 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className={`absolute inset-y-0 left-0 rounded-full bg-gradient-to-r ${getProgressBarColor()} transition-all duration-500 ease-out shadow-md`}
            style={{ width: `${displayPercent}%` }}
          >
            {/* Animated shine effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer" />
          </div>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Current Region */}
        {progress.region && (
          <div className="rounded-lg bg-blue-50 p-4 border border-blue-200">
            <div className="flex items-center gap-2 mb-1">
              <Cloud className="h-4 w-4 text-blue-600" />
              <span className="text-xs font-medium text-blue-700">Current Region</span>
            </div>
            <p className="text-lg font-bold text-blue-900">{progress.region}</p>
          </div>
        )}

        {/* Resources Found */}
        <div className="rounded-lg bg-orange-50 p-4 border border-orange-200">
          <div className="flex items-center gap-2 mb-1">
            <Database className="h-4 w-4 text-orange-600" />
            <span className="text-xs font-medium text-orange-700">Orphans Found</span>
          </div>
          <p className="text-lg font-bold text-orange-900">
            {progress.resources_found}
            {progress.resources_found > 0 && (
              <span className="text-sm text-orange-600 ml-1">
                resource{progress.resources_found > 1 ? "s" : ""}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Status Message */}
      {progress.state === "SUCCESS" && (
        <div className="mt-4 rounded-lg bg-green-50 border border-green-200 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <p className="text-sm font-medium text-green-800">
              Scan completed successfully! Found {progress.resources_found} orphaned resource
              {progress.resources_found !== 1 ? "s" : ""}.
            </p>
          </div>
        </div>
      )}

      {progress.state === "FAILURE" && (
        <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p className="text-sm font-medium text-red-800">
              Scan failed. Please check your credentials and try again.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// Add shimmer animation to global CSS or Tailwind config
// @keyframes shimmer {
//   0% { transform: translateX(-100%); }
//   100% { transform: translateX(100%); }
// }
// .animate-shimmer { animation: shimmer 2s infinite; }
