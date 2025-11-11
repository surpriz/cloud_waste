"use client";

import { useEffect, useState, useCallback } from "react";
import { X, Minimize2 } from "lucide-react";
import { scansAPI } from "@/lib/api";
import type { ScanProgress } from "@/types";
import { ScanProgressCard } from "./ScanProgressCard";

interface ScanProgressModalProps {
  scanId: string;
  accountName: string;
  isOpen: boolean;
  onClose: () => void;
  onComplete?: () => void;
}

/**
 * ScanProgressModal Component
 *
 * Full-screen modal that displays real-time scan progress.
 * Automatically polls for updates every 2 seconds until scan completes.
 */
export function ScanProgressModal({
  scanId,
  accountName,
  isOpen,
  onClose,
  onComplete,
}: ScanProgressModalProps) {
  const [progress, setProgress] = useState<ScanProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch progress from API
  const fetchProgress = useCallback(async () => {
    try {
      const data = await scansAPI.getProgress(scanId);
      setProgress(data);
      setError(null);

      // If scan completed or failed, notify parent and stop polling
      if (data.state === "SUCCESS" || data.state === "FAILURE") {
        if (onComplete) {
          onComplete();
        }
      }
    } catch (err) {
      console.error("Failed to fetch scan progress:", err);
      setError("Failed to fetch progress");
    }
  }, [scanId, onComplete]);

  // Poll for progress every 2 seconds while scan is active
  useEffect(() => {
    if (!isOpen) return;

    // Initial fetch
    fetchProgress();

    // Set up polling interval
    const interval = setInterval(() => {
      if (progress?.state === "PROGRESS" || progress?.state === "PENDING") {
        fetchProgress();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isOpen, fetchProgress, progress?.state]);

  // Close modal on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 animate-fade-in"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="pointer-events-auto w-full max-w-3xl animate-scale-in"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-3xl font-bold text-white drop-shadow-lg">
              Scanning Cloud Account
            </h2>
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="rounded-lg bg-white/20 backdrop-blur-sm p-3 text-white hover:bg-white/30 transition-colors border border-white/30"
                title="Minimize (continue in background)"
              >
                <Minimize2 className="h-5 w-5" />
              </button>
              <button
                onClick={onClose}
                className="rounded-lg bg-white/20 backdrop-blur-sm p-3 text-white hover:bg-white/30 transition-colors border border-white/30"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Progress Card */}
          {progress ? (
            <ScanProgressCard progress={progress} accountName={accountName} />
          ) : error ? (
            <div className="rounded-2xl border-2 border-red-200 bg-white p-8 shadow-xl">
              <p className="text-center text-red-600 font-medium">{error}</p>
            </div>
          ) : (
            <div className="rounded-2xl border-2 border-gray-200 bg-white p-8 shadow-xl">
              <div className="flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                <span className="ml-3 text-gray-600">Loading progress...</span>
              </div>
            </div>
          )}

          {/* Helper Text */}
          <p className="mt-4 text-center text-sm text-white/80 drop-shadow">
            You can minimize this window and the scan will continue in the background
          </p>
        </div>
      </div>
    </>
  );
}

// Add these animations to your Tailwind config or global CSS:
// @keyframes fade-in {
//   from { opacity: 0; }
//   to { opacity: 1; }
// }
// @keyframes scale-in {
//   from { transform: scale(0.95); opacity: 0; }
//   to { transform: scale(1); opacity: 1; }
// }
// .animate-fade-in { animation: fade-in 0.2s ease-out; }
// .animate-scale-in { animation: scale-in 0.2s ease-out; }
