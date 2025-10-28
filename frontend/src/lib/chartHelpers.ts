/**
 * Helper functions for preparing chart data
 */

import type { OrphanResource, OrphanResourceStats, ConfidenceLevel } from "@/types";

// Colors for charts
export const CHART_COLORS = {
  primary: "#3B82F6", // blue-500
  secondary: "#8B5CF6", // violet-500
  success: "#10B981", // green-500
  warning: "#F59E0B", // amber-500
  danger: "#EF4444", // red-500
  info: "#06B6D4", // cyan-500
  purple: "#A855F7", // purple-500
  pink: "#EC4899", // pink-500
  indigo: "#6366F1", // indigo-500
  teal: "#14B8A6", // teal-500
  orange: "#F97316", // orange-500
  lime: "#84CC16", // lime-500
};

export const CONFIDENCE_COLORS = {
  critical: "#DC2626", // red-600
  high: "#EA580C", // orange-600
  medium: "#CA8A04", // yellow-600
  low: "#16A34A", // green-600
};

/**
 * Calculate cost by resource type
 */
export function calculateCostByType(
  resources: OrphanResource[]
): Array<{ type: string; cost: number; count: number }> {
  const costMap = new Map<string, { cost: number; count: number }>();

  resources.forEach((resource) => {
    const existing = costMap.get(resource.resource_type) || { cost: 0, count: 0 };
    costMap.set(resource.resource_type, {
      cost: existing.cost + resource.estimated_monthly_cost,
      count: existing.count + 1,
    });
  });

  return Array.from(costMap.entries())
    .map(([type, data]) => ({
      type: formatResourceType(type),
      cost: data.cost,
      count: data.count,
    }))
    .sort((a, b) => b.cost - a.cost)
    .slice(0, 10); // Top 10
}

/**
 * Calculate confidence level distribution
 */
export function calculateConfidenceLevelDistribution(
  resources: OrphanResource[]
): Array<{ name: string; value: number; color: string }> {
  const counts: Record<ConfidenceLevel, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  };

  resources.forEach((resource) => {
    const level = extractConfidenceLevel(resource);
    if (level) {
      counts[level]++;
    }
  });

  return [
    {
      name: "Critical",
      value: counts.critical,
      color: CONFIDENCE_COLORS.critical,
    },
    {
      name: "High",
      value: counts.high,
      color: CONFIDENCE_COLORS.high,
    },
    {
      name: "Medium",
      value: counts.medium,
      color: CONFIDENCE_COLORS.medium,
    },
    {
      name: "Low",
      value: counts.low,
      color: CONFIDENCE_COLORS.low,
    },
  ].filter((item) => item.value > 0); // Only show non-zero values
}

/**
 * Extract confidence level from resource
 */
function extractConfidenceLevel(resource: OrphanResource): ConfidenceLevel | null {
  // Check direct property
  if (resource.confidence_level) {
    return resource.confidence_level;
  }

  // Check in metadata
  if (resource.resource_metadata?.confidence_level) {
    return resource.resource_metadata.confidence_level as ConfidenceLevel;
  }

  return null;
}

/**
 * Prepare data for type distribution pie chart
 */
export function prepareTypeDistributionData(
  stats: OrphanResourceStats | null
): Array<{ name: string; value: number; color: string }> {
  if (!stats || !stats.by_type) return [];

  const colors = [
    CHART_COLORS.primary,
    CHART_COLORS.secondary,
    CHART_COLORS.success,
    CHART_COLORS.warning,
    CHART_COLORS.danger,
    CHART_COLORS.info,
    CHART_COLORS.purple,
    CHART_COLORS.pink,
    CHART_COLORS.indigo,
    CHART_COLORS.teal,
    CHART_COLORS.orange,
    CHART_COLORS.lime,
  ];

  return Object.entries(stats.by_type)
    .map(([type, count], index) => ({
      name: formatResourceType(type),
      value: count,
      color: colors[index % colors.length] || CHART_COLORS.primary,
    }))
    .sort((a, b) => b.value - a.value);
}

/**
 * Prepare data for region distribution chart
 */
export function prepareRegionDistributionData(
  stats: OrphanResourceStats | null
): Array<{ name: string; value: number }> {
  if (!stats || !stats.by_region) return [];

  return Object.entries(stats.by_region)
    .map(([region, count]) => ({
      name: region,
      value: count,
    }))
    .sort((a, b) => b.value - a.value);
}

/**
 * Format resource type for display
 */
export function formatResourceType(type: string): string {
  // Convert snake_case to Title Case
  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Format currency
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format percentage
 */
export function formatPercentage(value: number, total: number): string {
  if (total === 0) return "0%";
  return `${((value / total) * 100).toFixed(1)}%`;
}
