"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useImpactStore } from "@/stores/useImpactStore";
import {
  DollarSign, Leaf, TrendingUp, Award, Zap, Target,
  Calendar, TreePine, Car, Home, Sparkles, Trophy,
  BarChart3, TrendingDown, Activity, Lock, Check, RefreshCw
} from "lucide-react";
import type { TimelineDataPoint } from "@/types/impact";

// Simple Line Chart Component (SVG-based)
interface SimpleLineChartProps {
  data: TimelineDataPoint[];
  width?: number;
  height?: number;
}

const SimpleLineChart = ({ data, width = 800, height = 300 }: SimpleLineChartProps) => {
  if (!data || data.length === 0) {
    return (
      <div className="w-full h-[300px] flex items-center justify-center text-gray-400">
        No data available
      </div>
    );
  }

  const maxValue = Math.max(...data.map(d => d.cumulative_savings), 1);
  const xScale = width / (data.length - 1 || 1);
  const yScale = height / maxValue;

  const points = data.map((d, i) => ({
    x: i * xScale,
    y: height - (d.cumulative_savings * yScale),
    value: d.cumulative_savings,
    date: d.date
  }));

  const pathD = points.map((p, i) =>
    `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
  ).join(' ');

  // Generate gradient area path
  const areaPathD = `${pathD} L ${width} ${height} L 0 ${height} Z`;

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
        <defs>
          <linearGradient id="chartGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* Area fill */}
        <path d={areaPathD} fill="url(#chartGradient)" />

        {/* Line */}
        <path d={pathD} fill="none" stroke="#3b82f6" strokeWidth="3" />

        {/* Points */}
        {points.map((p, i) => (
          <g key={i}>
            <circle
              cx={p.x}
              cy={p.y}
              r="5"
              fill="#3b82f6"
              className="hover:r-7 transition-all cursor-pointer"
            />
            <title>${p.value.toFixed(2)} on {p.date}</title>
          </g>
        ))}
      </svg>
    </div>
  );
};

// Hero Stat Card Component
interface HeroStatCardProps {
  icon: React.ReactNode;
  title: string;
  value: string;
  subtext: string;
  gradient: string;
  isLoading?: boolean;
}

const HeroStatCard = ({ icon, title, value, subtext, gradient, isLoading }: HeroStatCardProps) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl p-6 shadow-lg animate-pulse">
        <div className="h-12 w-12 bg-gray-200 rounded-xl mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-24 mb-2"></div>
        <div className="h-8 bg-gray-200 rounded w-32 mb-2"></div>
        <div className="h-3 bg-gray-200 rounded w-28"></div>
      </div>
    );
  }

  return (
    <div className={`bg-gradient-to-br ${gradient} rounded-2xl p-6 shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-1`}>
      <div className="flex items-start justify-between mb-4">
        <div className="bg-white/20 backdrop-blur-sm p-3 rounded-xl">
          {icon}
        </div>
      </div>
      <div>
        <p className="text-white/90 text-sm font-medium mb-1">{title}</p>
        <p className="text-white text-3xl font-bold mb-1">{value}</p>
        <p className="text-white/80 text-sm">{subtext}</p>
      </div>
    </div>
  );
};

// Achievement Badge Component
interface AchievementBadgeProps {
  name: string;
  description: string;
  icon: string;
  unlocked: boolean;
  progress: number;
  threshold: number;
  currentValue: number;
}

const AchievementBadge = ({
  name,
  description,
  icon,
  unlocked,
  progress,
  threshold,
  currentValue
}: AchievementBadgeProps) => {
  return (
    <div className={`relative rounded-xl p-6 transition-all duration-300 transform hover:scale-105 ${
      unlocked
        ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-200 shadow-md hover:shadow-lg'
        : 'bg-gray-50 border-2 border-gray-200 opacity-70'
    }`}>
      {/* Unlocked Checkmark */}
      {unlocked && (
        <div className="absolute top-2 right-2 bg-green-500 rounded-full p-1">
          <Check className="w-4 h-4 text-white" />
        </div>
      )}

      {/* Locked Icon */}
      {!unlocked && (
        <div className="absolute top-2 right-2 text-gray-400">
          <Lock className="w-5 h-5" />
        </div>
      )}

      {/* Icon */}
      <div className={`text-4xl mb-3 ${unlocked ? 'grayscale-0' : 'grayscale'}`}>
        {icon}
      </div>

      {/* Name & Description */}
      <h4 className={`font-bold text-lg mb-2 ${unlocked ? 'text-gray-900' : 'text-gray-500'}`}>
        {name}
      </h4>
      <p className={`text-sm mb-3 ${unlocked ? 'text-gray-600' : 'text-gray-400'}`}>
        {description}
      </p>

      {/* Progress Bar */}
      {!unlocked && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{currentValue}</span>
            <span>{threshold}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(progress * 100, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

// Quick Stat Card Component
interface QuickStatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}

const QuickStatCard = ({ icon, label, value, color }: QuickStatCardProps) => {
  return (
    <div className="bg-white rounded-xl p-5 shadow-md hover:shadow-lg transition-all duration-300 border border-gray-100">
      <div className="flex items-start space-x-4">
        <div className={`p-3 rounded-lg ${color}`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-gray-500 text-sm mb-1">{label}</p>
          <p className="text-gray-900 text-xl font-bold truncate" title={value}>{value}</p>
        </div>
      </div>
    </div>
  );
};

// Resource Type Breakdown Card
interface ResourceTypeBreakdownProps {
  resourceType: string;
  count: number;
  monthlyCost: number;
  totalCost: number;
}

const ResourceTypeBreakdown = ({
  resourceType,
  count,
  monthlyCost,
  totalCost
}: ResourceTypeBreakdownProps) => {
  const percentage = totalCost > 0 ? (monthlyCost / totalCost) * 100 : 0;

  return (
    <div className="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex justify-between items-start mb-2">
        <div>
          <p className="font-semibold text-gray-900">{resourceType}</p>
          <p className="text-sm text-gray-500">{count} resource{count !== 1 ? 's' : ''}</p>
        </div>
        <p className="text-lg font-bold text-blue-600">${monthlyCost.toFixed(2)}/mo</p>
      </div>

      {/* Percentage Bar */}
      <div className="space-y-1">
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 text-right">{percentage.toFixed(1)}% of total</p>
      </div>
    </div>
  );
};

// Main Page Component
export default function ImpactDashboardPage() {
  const router = useRouter();
  const {
    summary,
    timeline,
    achievements,
    quickStats,
    isLoading,
    error,
    fetchAll,
    clearError
  } = useImpactStore();

  const [selectedPeriod, setSelectedPeriod] = useState<"day" | "week" | "month" | "year" | "all">("month");

  // Fetch all data on mount and when period changes
  useEffect(() => {
    fetchAll(selectedPeriod);
  }, [selectedPeriod, fetchAll]);

  // Memoized calculations
  const sortedResourceTypes = useMemo(() => {
    if (!summary?.savings_by_resource_type) return [];

    return Object.entries(summary.savings_by_resource_type)
      .map(([type, cost]) => ({
        resourceType: type,
        count: summary.resources_by_resource_type[type] || 0,
        monthlyCost: cost
      }))
      .sort((a, b) => b.monthlyCost - a.monthlyCost);
  }, [summary]);

  const totalResourceTypeCost = useMemo(() => {
    return sortedResourceTypes.reduce((sum, item) => sum + item.monthlyCost, 0);
  }, [sortedResourceTypes]);

  // Loading State
  if (isLoading && !summary) {
    return (
      <div className="p-8 space-y-8">
        {/* Header Skeleton */}
        <div className="animate-pulse">
          <div className="h-10 bg-gray-200 rounded w-96 mb-3"></div>
          <div className="h-6 bg-gray-200 rounded w-[500px]"></div>
        </div>

        {/* Hero Cards Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gray-100 rounded-2xl p-6 h-48 animate-pulse"></div>
          ))}
        </div>

        {/* Chart Skeleton */}
        <div className="bg-white rounded-2xl p-6 shadow-lg">
          <div className="h-8 bg-gray-200 rounded w-48 mb-6"></div>
          <div className="h-[300px] bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  // Error State
  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border-2 border-red-200 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-2">
            <div className="bg-red-500 text-white p-2 rounded-lg">
              <Activity className="w-6 h-6" />
            </div>
            <h3 className="text-red-900 font-bold text-xl">Error Loading Impact Data</h3>
          </div>
          <p className="text-red-700 mb-4">{error}</p>
          <button
            onClick={() => {
              clearError();
              fetchAll(selectedPeriod);
            }}
            className="bg-red-500 hover:bg-red-600 text-white px-6 py-2 rounded-lg font-semibold transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty State
  if (!summary || summary.total_resources_detected === 0) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[600px]">
        <div className="text-center max-w-md">
          <div className="bg-gradient-to-br from-blue-100 to-purple-100 w-32 h-32 rounded-full flex items-center justify-center mx-auto mb-6">
            <Sparkles className="w-16 h-16 text-blue-600" />
          </div>
          <h2 className="text-3xl font-bold text-gray-900 mb-4">No Impact Data Yet</h2>
          <p className="text-gray-600 mb-8 text-lg">
            Start by scanning your cloud accounts to discover orphaned resources and begin tracking your environmental and financial impact!
          </p>
          <button
            onClick={() => router.push('/dashboard/scans')}
            className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
          >
            Start Your First Scan
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header Section */}
      <div className="text-center mb-8 relative">
        <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-3">
          Your CloudWaste Impact Report 🎉
        </h1>
        <p className="text-gray-600 text-lg md:text-xl mb-4">
          Since you started using CloudWaste, here&apos;s your positive impact...
        </p>
        <button
          onClick={() => fetchAll(selectedPeriod)}
          disabled={isLoading}
          className="inline-flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg font-semibold transition-all duration-300 transform hover:scale-105 disabled:scale-100 disabled:cursor-not-allowed shadow-md"
          title="Refresh data"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>{isLoading ? 'Refreshing...' : 'Refresh Data'}</span>
        </button>
      </div>

      {/* Hero Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <HeroStatCard
          icon={<DollarSign className="w-8 h-8 text-white" />}
          title="Total Savings"
          value={`$${summary.total_monthly_savings.toFixed(2)}/mo`}
          subtext={`$${summary.total_annual_savings.toFixed(2)}/year`}
          gradient="from-green-500 to-emerald-600"
          isLoading={isLoading}
        />

        <HeroStatCard
          icon={<Leaf className="w-8 h-8 text-white" />}
          title="CO2 Saved"
          value={`${summary.total_co2_saved_kg.toFixed(0)} kg`}
          subtext={`= ${summary.trees_equivalent.toFixed(1)} trees 🌳`}
          gradient="from-blue-500 to-cyan-600"
          isLoading={isLoading}
        />

        <HeroStatCard
          icon={<Target className="w-8 h-8 text-white" />}
          title="Resources Cleaned"
          value={`${summary.total_resources_deleted}`}
          subtext={`${summary.total_resources_active} still active`}
          gradient="from-purple-500 to-pink-600"
          isLoading={isLoading}
        />

        <HeroStatCard
          icon={<Trophy className="w-8 h-8 text-white" />}
          title="Cleanup Rate"
          value={`${(summary.cleanup_rate * 100).toFixed(0)}%`}
          subtext={`${summary.cleanup_streak_days} day streak 🔥`}
          gradient="from-orange-500 to-red-600"
          isLoading={isLoading}
        />
      </div>

      {/* Savings Timeline Chart */}
      <div className="bg-white rounded-2xl p-6 shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 md:mb-0 flex items-center space-x-2">
            <TrendingUp className="w-7 h-7 text-blue-600" />
            <span>Savings Timeline</span>
          </h2>

          {/* Period Selector */}
          <div className="flex space-x-2 bg-gray-100 p-1 rounded-lg">
            {(['day', 'week', 'month', 'year', 'all'] as const).map((period) => (
              <button
                key={period}
                onClick={() => setSelectedPeriod(period)}
                className={`px-4 py-2 rounded-md font-semibold text-sm transition-all duration-200 ${
                  selectedPeriod === period
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'text-gray-600 hover:bg-gray-200'
                }`}
              >
                {period.charAt(0).toUpperCase() + period.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Chart */}
        <div className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-xl p-6">
          {timeline?.data_points && timeline.data_points.length > 0 ? (
            <SimpleLineChart data={timeline.data_points} />
          ) : (
            <div className="h-[300px] flex items-center justify-center text-gray-400">
              <p>No timeline data available for this period</p>
            </div>
          )}
        </div>

        {/* Chart Legend */}
        {timeline?.summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
            <div className="text-center">
              <p className="text-gray-500 text-sm">Resources Detected</p>
              <p className="text-2xl font-bold text-gray-900">
                {timeline.summary.total_resources_detected || 0}
              </p>
            </div>
            <div className="text-center">
              <p className="text-gray-500 text-sm">Resources Deleted</p>
              <p className="text-2xl font-bold text-green-600">
                {timeline.summary.total_resources_deleted || 0}
              </p>
            </div>
            <div className="text-center">
              <p className="text-gray-500 text-sm">Total Savings</p>
              <p className="text-2xl font-bold text-blue-600">
                ${(timeline.summary.total_savings || 0).toFixed(2)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-gray-500 text-sm">CO2 Saved</p>
              <p className="text-2xl font-bold text-cyan-600">
                {(timeline.summary.total_co2_saved || 0).toFixed(0)} kg
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Environmental Impact Section */}
      <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-8 shadow-lg border-2 border-green-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center space-x-2">
          <Leaf className="w-7 h-7 text-green-600" />
          <span>🌍 Environmental Impact Breakdown</span>
        </h2>

        {/* Impact Comparisons */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl p-6 shadow-md">
            <div className="flex items-center space-x-4 mb-3">
              <div className="bg-green-100 p-3 rounded-lg">
                <TreePine className="w-8 h-8 text-green-600" />
              </div>
              <div>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.trees_equivalent.toFixed(1)}
                </p>
                <p className="text-sm text-gray-500">trees</p>
              </div>
            </div>
            <p className="text-gray-600">
              Trees planted for 1 year 🌳
            </p>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-md">
            <div className="flex items-center space-x-4 mb-3">
              <div className="bg-blue-100 p-3 rounded-lg">
                <Car className="w-8 h-8 text-blue-600" />
              </div>
              <div>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.car_km_equivalent.toFixed(0)}
                </p>
                <p className="text-sm text-gray-500">km</p>
              </div>
            </div>
            <p className="text-gray-600">
              Distance not driven by car 🚗
            </p>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-md">
            <div className="flex items-center space-x-4 mb-3">
              <div className="bg-purple-100 p-3 rounded-lg">
                <Home className="w-8 h-8 text-purple-600" />
              </div>
              <div>
                <p className="text-3xl font-bold text-gray-900">
                  {summary.home_days_equivalent.toFixed(1)}
                </p>
                <p className="text-sm text-gray-500">days</p>
              </div>
            </div>
            <p className="text-gray-600">
              Home electricity saved 🏠
            </p>
          </div>
        </div>

        {/* Provider Breakdown */}
        <div className="bg-white rounded-xl p-6 shadow-md">
          <h3 className="font-bold text-lg text-gray-900 mb-4">CO2 by Cloud Provider</h3>
          <div className="space-y-3">
            {Object.entries(summary.co2_by_provider).map(([provider, co2]) => {
              const totalCO2 = Object.values(summary.co2_by_provider).reduce((a, b) => a + b, 0);
              const percentage = totalCO2 > 0 ? (co2 / totalCO2) * 100 : 0;

              return (
                <div key={provider}>
                  <div className="flex justify-between mb-1">
                    <span className="font-semibold text-gray-700">{provider.toUpperCase()}</span>
                    <span className="text-gray-900 font-bold">{co2.toFixed(2)} kg CO2</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-gradient-to-r from-green-500 to-emerald-600 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Achievements Gallery */}
      {achievements && achievements.achievements.length > 0 && (
        <div className="bg-white rounded-2xl p-8 shadow-lg">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center space-x-2">
              <Trophy className="w-7 h-7 text-yellow-600" />
              <span>🏆 Your Achievements</span>
            </h2>
            <div className="text-right">
              <p className="text-sm text-gray-500">Progress</p>
              <p className="text-2xl font-bold text-gray-900">
                {achievements.total_unlocked} / {achievements.total_available}
              </p>
              <p className="text-sm text-blue-600 font-semibold">
                {(achievements.completion_rate * 100).toFixed(0)}% Complete
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {achievements.achievements.map((achievement) => (
              <AchievementBadge
                key={achievement.id}
                name={achievement.name}
                description={achievement.description}
                icon={achievement.icon}
                unlocked={achievement.unlocked}
                progress={achievement.progress}
                threshold={achievement.threshold}
                currentValue={achievement.current_value}
              />
            ))}
          </div>
        </div>
      )}

      {/* Quick Stats */}
      {quickStats && (
        <div className="bg-white rounded-2xl p-8 shadow-lg">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center space-x-2">
            <Zap className="w-7 h-7 text-yellow-600" />
            <span>🔥 Interesting Facts</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <QuickStatCard
              icon={<Award className="w-6 h-6 text-yellow-600" />}
              label="Biggest Cleanup"
              value={`$${quickStats.biggest_cleanup_monthly_cost.toFixed(2)}/mo`}
              color="bg-yellow-50"
            />

            <QuickStatCard
              icon={<BarChart3 className="w-6 h-6 text-blue-600" />}
              label="Most Common Type"
              value={quickStats.most_common_resource_type || 'N/A'}
              color="bg-blue-50"
            />

            <QuickStatCard
              icon={<Zap className="w-6 h-6 text-purple-600" />}
              label="Fastest Cleanup"
              value={
                quickStats.fastest_cleanup_hours !== null
                  ? `${quickStats.fastest_cleanup_hours.toFixed(1)}h`
                  : 'N/A'
              }
              color="bg-purple-50"
            />

            <QuickStatCard
              icon={<Target className="w-6 h-6 text-green-600" />}
              label="Top Region"
              value={quickStats.top_region || 'N/A'}
              color="bg-green-50"
            />
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            <QuickStatCard
              icon={<Calendar className="w-6 h-6 text-red-600" />}
              label="Avg Resource Age"
              value={`${quickStats.average_resource_age_days.toFixed(0)} days`}
              color="bg-red-50"
            />

            <QuickStatCard
              icon={<Activity className="w-6 h-6 text-indigo-600" />}
              label="Most Common Count"
              value={`${quickStats.most_common_resource_count} resources`}
              color="bg-indigo-50"
            />
          </div>
        </div>
      )}

      {/* Breakdown by Resource Type */}
      {sortedResourceTypes.length > 0 && (
        <div className="bg-white rounded-2xl p-8 shadow-lg">
          <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center space-x-2">
            <BarChart3 className="w-7 h-7 text-blue-600" />
            <span>📊 Savings by Resource Type</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sortedResourceTypes.map((item) => (
              <ResourceTypeBreakdown
                key={item.resourceType}
                resourceType={item.resourceType}
                count={item.count}
                monthlyCost={item.monthlyCost}
                totalCost={totalResourceTypeCost}
              />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations Section */}
      {summary.total_resources_active > 0 && summary.potential_monthly_savings > 0 && (
        <div className="bg-gradient-to-br from-orange-50 to-yellow-50 rounded-2xl p-8 shadow-lg border-2 border-orange-200">
          <div className="flex items-start space-x-4">
            <div className="bg-orange-500 text-white p-4 rounded-xl">
              <TrendingDown className="w-8 h-8" />
            </div>
            <div className="flex-1">
              <h2 className="text-2xl font-bold text-gray-900 mb-3">
                💡 Potential Savings Available
              </h2>
              <p className="text-gray-700 text-lg mb-4">
                You have <span className="font-bold text-orange-600">{summary.total_resources_active}</span> resources
                worth <span className="font-bold text-orange-600">${summary.potential_monthly_savings.toFixed(2)}/month</span> marked
                for deletion. Delete them to increase your savings!
              </p>
              <button
                onClick={() => router.push('/dashboard/resources')}
                className="bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white px-8 py-3 rounded-lg font-bold shadow-md hover:shadow-lg transition-all duration-300 transform hover:-translate-y-1"
              >
                View Resources to Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer Stats */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-8 shadow-lg text-white">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div>
            <p className="text-white/80 mb-2">Days Since First Scan</p>
            <p className="text-4xl font-bold">{summary.days_since_first_scan}</p>
          </div>
          <div>
            <p className="text-white/80 mb-2">Already Wasted (Total)</p>
            <p className="text-4xl font-bold">${summary.already_wasted_total.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-white/80 mb-2">Resources Ignored</p>
            <p className="text-4xl font-bold">{summary.total_resources_ignored}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
