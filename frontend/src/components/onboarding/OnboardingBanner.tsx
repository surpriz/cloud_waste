"use client";

import { X, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useOnboarding } from "@/hooks/useOnboarding";

/**
 * Onboarding Banner Component
 *
 * Compact, persistent banner shown at top of all dashboard pages
 * until onboarding is completed or dismissed.
 */
export function OnboardingBanner() {
  const {
    checklistItems,
    isChecklistComplete,
    dismissed,
    progressPercentage,
    skipOnboarding,
    navigateToOnboarding,
  } = useOnboarding();

  const completedCount = checklistItems.filter((item) => item.completed).length;
  const totalCount = checklistItems.length;

  // Debug logs (remove in production)
  if (typeof window !== "undefined") {
    console.log("[OnboardingBanner] State:", {
      isChecklistComplete,
      dismissed,
      progressPercentage,
      completedCount,
      totalCount,
    });
  }

  // Don't show if completed or dismissed
  if (isChecklistComplete || dismissed) {
    return null;
  }

  return (
    <div className="relative overflow-hidden rounded-xl border-2 border-blue-300 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 p-4 shadow-lg">
      {/* Animated background elements */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-0 right-0 h-32 w-32 rounded-full bg-white blur-2xl animate-pulse"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 flex items-center justify-between gap-4">
        {/* Left side: Progress and text */}
        <div className="flex items-center gap-4 flex-1">
          {/* Progress circle */}
          <div className="relative flex-shrink-0">
            <svg className="h-12 w-12 transform -rotate-90">
              <circle
                cx="24"
                cy="24"
                r="18"
                stroke="currentColor"
                strokeWidth="3"
                fill="none"
                className="text-white/30"
              />
              <circle
                cx="24"
                cy="24"
                r="18"
                stroke="currentColor"
                strokeWidth="3"
                fill="none"
                strokeDasharray={`${2 * Math.PI * 18}`}
                strokeDashoffset={`${
                  2 * Math.PI * 18 * (1 - progressPercentage / 100)
                }`}
                className="text-white transition-all duration-500"
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs font-bold text-white">
                {progressPercentage}%
              </span>
            </div>
          </div>

          {/* Text */}
          <div className="flex-1 min-w-0">
            <h3 className="text-base md:text-lg font-bold text-white mb-1">
              🚀 Complete Your Setup
            </h3>
            <p className="text-sm text-white/90">
              {completedCount} of {totalCount} steps completed • Get the most out of CutCosts
            </p>
          </div>

          {/* Checklist items (hidden on mobile) */}
          <div className="hidden lg:flex items-center gap-2">
            {checklistItems.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.id}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    item.completed
                      ? "bg-green-500/20 text-white border border-green-400/30"
                      : "bg-white/10 text-white/80 border border-white/20"
                  }`}
                  title={item.description}
                >
                  {Icon && <Icon className="h-3.5 w-3.5" />}
                  <span className="whitespace-nowrap">{item.label}</span>
                  {item.completed && <span className="ml-1">✓</span>}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right side: Action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={navigateToOnboarding}
            className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-purple-600 hover:bg-white/90 transition-all shadow-md hover:shadow-lg"
          >
            <span className="hidden sm:inline">Continue Setup</span>
            <span className="sm:hidden">Continue</span>
            <ArrowRight className="h-4 w-4" />
          </button>

          <button
            onClick={skipOnboarding}
            className="rounded-lg p-2 text-white/80 hover:bg-white/10 transition-colors"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
