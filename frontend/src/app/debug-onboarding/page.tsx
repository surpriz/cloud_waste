"use client";

import { useOnboardingStore } from "@/stores/useOnboardingStore";
import { useRouter } from "next/navigation";
import { RefreshCw, Trash2, Eye } from "lucide-react";

/**
 * Debug page for onboarding
 *
 * Use this to reset onboarding state or view current state
 * Access: http://localhost:3000/debug-onboarding
 */
export default function DebugOnboardingPage() {
  const router = useRouter();
  const store = useOnboardingStore();

  const handleReset = () => {
    store.resetOnboarding();
    // Note: Storage is now user-scoped, so resetOnboarding() handles cleanup
    alert("Onboarding reset! Redirecting to dashboard...");
    router.push("/dashboard");
  };

  const handleClearLocalStorage = () => {
    localStorage.clear();
    alert("All localStorage cleared! Reload the page.");
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          🔧 Onboarding Debug Panel
        </h1>

        {/* Current State */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Current State
          </h2>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Completed</p>
              <p className="text-2xl font-bold text-gray-900">
                {store.isCompleted ? "✅ Yes" : "❌ No"}
              </p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Dismissed</p>
              <p className="text-2xl font-bold text-gray-900">
                {store.dismissed ? "✅ Yes" : "❌ No"}
              </p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Account Added</p>
              <p className="text-2xl font-bold text-gray-900">
                {store.accountAdded ? "✅ Yes" : "❌ No"}
              </p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">First Scan</p>
              <p className="text-2xl font-bold text-gray-900">
                {store.firstScanCompleted ? "✅ Yes" : "❌ No"}
              </p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Results Reviewed</p>
              <p className="text-2xl font-bold text-gray-900">
                {store.resultsReviewed ? "✅ Yes" : "❌ No"}
              </p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Current Step</p>
              <p className="text-xl font-bold text-gray-900">
                {store.currentStep}
              </p>
            </div>
          </div>

          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Completed Steps</p>
            <p className="text-sm font-mono text-gray-900">
              {store.completedSteps.length > 0
                ? store.completedSteps.join(", ")
                : "None"}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Actions</h2>

          <div className="space-y-4">
            <button
              onClick={handleReset}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 py-4 text-lg font-semibold text-white hover:bg-blue-700 transition-colors"
            >
              <RefreshCw className="h-5 w-5" />
              Reset Onboarding State
            </button>

            <button
              onClick={handleClearLocalStorage}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-red-600 px-6 py-4 text-lg font-semibold text-white hover:bg-red-700 transition-colors"
            >
              <Trash2 className="h-5 w-5" />
              Clear All LocalStorage (Nuclear Option)
            </button>

            <button
              onClick={() => router.push("/dashboard")}
              className="w-full flex items-center justify-center gap-2 rounded-xl border-2 border-gray-300 bg-white px-6 py-4 text-lg font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Back to Dashboard
            </button>

            <button
              onClick={() => router.push("/onboarding")}
              className="w-full flex items-center justify-center gap-2 rounded-xl border-2 border-purple-300 bg-purple-50 px-6 py-4 text-lg font-semibold text-purple-700 hover:bg-purple-100 transition-colors"
            >
              Go to Onboarding Wizard
            </button>
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-6 bg-yellow-50 border-2 border-yellow-300 rounded-xl p-6">
          <h3 className="font-bold text-yellow-900 mb-2">📋 Instructions</h3>
          <ul className="text-sm text-yellow-800 space-y-1">
            <li>• If banner not showing: Click "Reset Onboarding State"</li>
            <li>• If still issues: Click "Clear All LocalStorage" and reload</li>
            <li>• Check browser console for [OnboardingBanner] logs</li>
            <li>• After reset, go to dashboard to see banner</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
