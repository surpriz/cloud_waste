"use client";

import {
  CheckCircle,
  Sparkles,
  LayoutDashboard,
  TrendingDown,
  Zap,
} from "lucide-react";

interface CompletionStepProps {
  onFinish: () => void;
}

/**
 * Completion Step - Final onboarding step
 *
 * Celebrates completion and guides user to dashboard
 */
export function CompletionStep({ onFinish }: CompletionStepProps) {
  const achievements = [
    {
      icon: CheckCircle,
      title: "Account Connected",
      description: "Successfully linked your cloud provider",
      color: "text-green-600",
      bg: "bg-green-100",
    },
    {
      icon: Zap,
      title: "First Scan Complete",
      description: "Analyzed your cloud infrastructure",
      color: "text-purple-600",
      bg: "bg-purple-100",
    },
    {
      icon: TrendingDown,
      title: "Waste Detected",
      description: "Identified cost-saving opportunities",
      color: "text-orange-600",
      bg: "bg-orange-100",
    },
  ];

  return (
    <div className="text-center max-w-4xl mx-auto">
      {/* Success animation */}
      <div className="mb-8">
        <div className="relative inline-block">
          <div className="absolute inset-0 bg-gradient-to-br from-green-600 to-emerald-600 rounded-full blur-2xl opacity-30 animate-pulse"></div>
          <div className="relative inline-flex items-center justify-center h-24 w-24 rounded-full bg-gradient-to-br from-green-600 to-emerald-600 shadow-2xl mb-6">
            <CheckCircle className="h-12 w-12 text-white" />
          </div>
        </div>

        <h2 className="text-4xl md:text-5xl font-extrabold bg-gradient-to-r from-green-600 via-blue-600 to-purple-600 bg-clip-text text-transparent mb-3">
          Congratulations! 🎉
        </h2>

        <p className="text-xl text-gray-600 mb-2">
          You're All Set to Start Saving Money
        </p>

        <p className="text-lg text-gray-500">
          CloudWaste is now monitoring your cloud for wasteful spending
        </p>
      </div>

      {/* Achievement badges */}
      <div className="grid gap-4 md:grid-cols-3 mb-10">
        {achievements.map((achievement) => {
          const Icon = achievement.icon;
          return (
            <div
              key={achievement.title}
              className="rounded-2xl border-2 border-gray-200 bg-white p-6 hover:shadow-lg transition-shadow"
            >
              <div
                className={`inline-flex items-center justify-center h-14 w-14 rounded-full ${achievement.bg} mb-4`}
              >
                <Icon className={`h-7 w-7 ${achievement.color}`} />
              </div>

              <h3 className="text-lg font-bold text-gray-900 mb-2">
                {achievement.title}
              </h3>

              <p className="text-sm text-gray-600">{achievement.description}</p>
            </div>
          );
        })}
      </div>

      {/* What's next */}
      <div className="rounded-2xl border border-gray-200 bg-gradient-to-br from-blue-50 to-purple-50 p-8 mb-8">
        <div className="flex items-center justify-center gap-2 mb-4">
          <Sparkles className="h-6 w-6 text-blue-600" />
          <h3 className="text-2xl font-bold text-gray-900">What's Next?</h3>
        </div>

        <p className="text-gray-700 mb-6 max-w-2xl mx-auto">
          Your dashboard is ready with real-time insights, cost analytics, and
          actionable recommendations to help you optimize your cloud spend.
        </p>

        <div className="grid gap-4 md:grid-cols-2 text-left max-w-2xl mx-auto mb-6">
          <div className="flex items-start gap-3 p-4 rounded-xl bg-white border border-gray-200">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 flex-shrink-0">
              <span className="text-blue-600 font-bold">1</span>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">
                Review Resources
              </h4>
              <p className="text-sm text-gray-600">
                Check detected orphans and decide which to keep or remove
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-4 rounded-xl bg-white border border-gray-200">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 flex-shrink-0">
              <span className="text-purple-600 font-bold">2</span>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">
                Schedule Scans
              </h4>
              <p className="text-sm text-gray-600">
                Set up automatic daily scans to stay on top of waste
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-4 rounded-xl bg-white border border-gray-200">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100 flex-shrink-0">
              <span className="text-green-600 font-bold">3</span>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">
                Track Savings
              </h4>
              <p className="text-sm text-gray-600">
                Monitor your cost optimization over time
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-4 rounded-xl bg-white border border-gray-200">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 flex-shrink-0">
              <span className="text-orange-600 font-bold">4</span>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">
                Add More Accounts
              </h4>
              <p className="text-sm text-gray-600">
                Connect additional cloud accounts for full visibility
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={onFinish}
        className="group inline-flex items-center gap-3 rounded-xl bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 px-10 py-5 text-xl font-bold text-white shadow-2xl hover:shadow-3xl transition-all hover:scale-105"
      >
        <LayoutDashboard className="h-6 w-6 group-hover:rotate-12 transition-transform" />
        Go to Dashboard
        <Sparkles className="h-6 w-6 group-hover:rotate-12 transition-transform" />
      </button>

      <p className="mt-6 text-sm text-gray-500">
        🚀 You can restart this tutorial anytime from Settings
      </p>
    </div>
  );
}
