"use client";

import { useState } from "react";
import { Check, ChevronDown, ChevronUp, X, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useOnboarding } from "@/hooks/useOnboarding";

/**
 * Onboarding Checklist Component
 *
 * Shows progress checklist in dashboard until onboarding is complete
 * Collapsible and dismissible
 */
export function OnboardingChecklist() {
  const {
    checklistItems,
    isChecklistComplete,
    progressPercentage,
    skipOnboarding,
    navigateToOnboarding,
  } = useOnboarding();

  const [isExpanded, setIsExpanded] = useState(true);
  const [isDismissed, setIsDismissed] = useState(false);

  const completedCount = checklistItems.filter((item) => item.completed).length;
  const totalCount = checklistItems.length;

  // Don't show if completed or dismissed
  if (isChecklistComplete || isDismissed) {
    return null;
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border-2 border-blue-300 bg-gradient-to-br from-blue-50 to-purple-50 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-blue-200">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative">
            <svg className="h-12 w-12 transform -rotate-90">
              <circle
                cx="24"
                cy="24"
                r="20"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
                className="text-blue-200"
              />
              <circle
                cx="24"
                cy="24"
                r="20"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
                strokeDasharray={`${2 * Math.PI * 20}`}
                strokeDashoffset={`${
                  2 * Math.PI * 20 * (1 - progressPercentage / 100)
                }`}
                className="text-blue-600 transition-all duration-500"
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs font-bold text-blue-600">
                {progressPercentage}%
              </span>
            </div>
          </div>

          <div className="flex-1">
            <h3 className="text-lg font-bold text-gray-900">
              Getting Started
            </h3>
            <p className="text-sm text-gray-600">
              {completedCount} of {totalCount} completed
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="rounded-lg p-2 text-gray-600 hover:bg-white/50 transition-colors"
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? (
              <ChevronUp className="h-5 w-5" />
            ) : (
              <ChevronDown className="h-5 w-5" />
            )}
          </button>

          <button
            onClick={() => {
              setIsDismissed(true);
              skipOnboarding();
            }}
            className="rounded-lg p-2 text-gray-600 hover:bg-white/50 transition-colors"
            aria-label="Dismiss"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Checklist items */}
      {isExpanded && (
        <div className="p-4 space-y-3">
          {checklistItems.map((item) => {
            const Icon = item.icon;

            return (
              <div
                key={item.id}
                className={`flex items-start gap-3 p-3 rounded-xl border-2 transition-all ${
                  item.completed
                    ? "border-green-300 bg-green-50"
                    : "border-gray-200 bg-white hover:border-blue-300"
                }`}
              >
                <div
                  className={`flex items-center justify-center h-6 w-6 rounded-full flex-shrink-0 ${
                    item.completed
                      ? "bg-green-600"
                      : "border-2 border-gray-300 bg-white"
                  }`}
                >
                  {item.completed && <Check className="h-4 w-4 text-white" />}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {Icon && <Icon className="h-4 w-4 text-gray-600" />}
                    <h4
                      className={`font-semibold text-sm ${
                        item.completed
                          ? "text-green-900 line-through"
                          : "text-gray-900"
                      }`}
                    >
                      {item.label}
                    </h4>
                  </div>

                  {item.description && (
                    <p className="text-xs text-gray-600 mb-2">
                      {item.description}
                    </p>
                  )}

                  {!item.completed && item.route && (
                    <Link
                      href={item.route}
                      className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 transition-colors"
                    >
                      Go to setup
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  )}
                </div>
              </div>
            );
          })}

          {/* Continue tutorial button */}
          {progressPercentage < 100 && progressPercentage > 0 && (
            <button
              onClick={navigateToOnboarding}
              className="w-full mt-4 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-3 text-sm font-semibold text-white hover:shadow-lg transition-all"
            >
              Continue Setup Tutorial
            </button>
          )}
        </div>
      )}
    </div>
  );
}
