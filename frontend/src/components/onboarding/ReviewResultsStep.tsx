"use client";

import { Eye, DollarSign, AlertTriangle, TrendingDown, ArrowRight } from "lucide-react";
import { useResourceStore } from "@/stores/useResourceStore";
import Link from "next/link";

interface ReviewResultsStepProps {
  onNext: () => void;
}

/**
 * Review Results Step - Fourth onboarding step
 *
 * Shows preview of scan results and encourages exploration
 */
export function ReviewResultsStep({ onNext }: ReviewResultsStepProps) {
  const { stats, resources } = useResourceStore();

  const hasResources = (stats?.total_resources || 0) > 0;
  const topResources = resources
    .sort((a, b) => b.estimated_monthly_cost - a.estimated_monthly_cost)
    .slice(0, 3);

  return (
    <div className="text-center max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-orange-600 to-red-600 shadow-lg mb-4">
          <Eye className="h-8 w-8 text-white" />
        </div>

        <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mb-3">
          Review Your Results
        </h2>

        <p className="text-lg text-gray-600">
          Here's what we found in your cloud infrastructure
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid gap-6 md:grid-cols-3 mb-8">
        <div className="rounded-2xl border-2 border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50 p-6">
          <div className="inline-flex items-center justify-center h-12 w-12 rounded-xl bg-orange-600 mb-3">
            <AlertTriangle className="h-6 w-6 text-white" />
          </div>
          <p className="text-sm text-gray-600 mb-1">Waste Detected</p>
          <p className="text-4xl font-extrabold text-orange-600">
            {stats?.total_resources || 0}
          </p>
        </div>

        <div className="rounded-2xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 p-6">
          <div className="inline-flex items-center justify-center h-12 w-12 rounded-xl bg-green-600 mb-3">
            <DollarSign className="h-6 w-6 text-white" />
          </div>
          <p className="text-sm text-gray-600 mb-1">Monthly Savings</p>
          <p className="text-4xl font-extrabold text-green-600">
            ${(stats?.total_monthly_cost || 0).toFixed(0)}
          </p>
        </div>

        <div className="rounded-2xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-cyan-50 p-6">
          <div className="inline-flex items-center justify-center h-12 w-12 rounded-xl bg-blue-600 mb-3">
            <TrendingDown className="h-6 w-6 text-white" />
          </div>
          <p className="text-sm text-gray-600 mb-1">Annual Savings</p>
          <p className="text-4xl font-extrabold text-blue-600">
            ${((stats?.total_monthly_cost || 0) * 12).toFixed(0)}
          </p>
        </div>
      </div>

      {/* Top offenders or empty state */}
      {hasResources ? (
        <div className="mb-8 rounded-2xl border border-gray-200 bg-white p-8 shadow-lg text-left">
          <h3 className="text-2xl font-bold text-gray-900 mb-4 text-center">
            Top Cost Offenders
          </h3>

          <div className="space-y-3 mb-6">
            {topResources.map((resource, index) => (
              <div
                key={resource.id}
                className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-gray-50 to-gray-100 hover:from-orange-50 hover:to-amber-50 transition-all"
              >
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-orange-100 text-orange-700 font-bold text-sm flex-shrink-0">
                  {index + 1}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">
                    {resource.resource_type.replace(/_/g, " ").toUpperCase()}
                  </p>
                  <p className="text-sm text-gray-600 truncate">
                    {resource.resource_name || resource.resource_id}
                  </p>
                </div>

                <div className="text-right flex-shrink-0">
                  <p className="font-bold text-lg text-gray-900">
                    ${resource.estimated_monthly_cost.toFixed(2)}
                  </p>
                  <p className="text-xs text-gray-500">/month</p>
                </div>
              </div>
            ))}
          </div>

          <p className="text-center text-gray-600 mb-6">
            {stats && stats.total_resources > 3 && (
              <>
                And <strong>{stats.total_resources - 3} more</strong> orphaned
                resources waiting to be reviewed
              </>
            )}
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/dashboard/resources"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-orange-600 to-red-600 px-6 py-3 font-semibold text-white hover:shadow-lg transition-all"
            >
              <Eye className="h-5 w-5" />
              View All Resources
            </Link>

            <button
              onClick={onNext}
              className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Continue
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="mb-8 rounded-2xl border-2 border-dashed border-green-300 bg-green-50 p-8">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
            <AlertTriangle className="h-8 w-8 text-green-600" />
          </div>

          <h3 className="text-2xl font-bold text-green-900 mb-3">
            Great News! No Major Waste Detected
          </h3>

          <p className="text-green-700 mb-6 max-w-xl mx-auto">
            Your cloud infrastructure looks clean! We didn't find any obvious
            orphaned resources or wasteful spending. Keep monitoring regularly to
            stay optimized.
          </p>

          <button
            onClick={onNext}
            className="inline-flex items-center gap-2 rounded-xl bg-green-600 px-8 py-4 text-lg font-semibold text-white hover:bg-green-700 transition-colors shadow-lg"
          >
            Complete Onboarding
            <ArrowRight className="h-5 w-5" />
          </button>
        </div>
      )}

      {/* Educational tip */}
      <div className="rounded-xl bg-blue-50 border border-blue-200 p-4">
        <p className="text-sm text-blue-800">
          💡 <strong>Pro Tip:</strong> Schedule automatic daily scans to
          continuously monitor your cloud for new waste. You can set this up in
          Settings.
        </p>
      </div>
    </div>
  );
}
