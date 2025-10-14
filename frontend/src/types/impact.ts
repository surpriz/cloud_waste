/**
 * TypeScript type definitions for Impact & Savings Dashboard
 */

export interface ImpactSummary {
  // Financial Impact
  total_resources_detected: number;
  total_resources_deleted: number;
  total_resources_active: number;
  total_resources_ignored: number;

  total_monthly_savings: number;
  total_annual_savings: number;
  potential_monthly_savings: number;
  already_wasted_total: number;

  // Environmental Impact
  total_co2_saved_kg: number;
  trees_equivalent: number;
  car_km_equivalent: number;
  home_days_equivalent: number;

  // Breakdowns
  savings_by_provider: Record<string, number>;
  co2_by_provider: Record<string, number>;
  savings_by_resource_type: Record<string, number>;
  resources_by_resource_type: Record<string, number>;

  // User Engagement
  cleanup_rate: number;
  first_scan_date: string | null;
  days_since_first_scan: number;
  last_cleanup_date: string | null;
  cleanup_streak_days: number;
}

export interface TimelineDataPoint {
  date: string;
  resources_detected: number;
  resources_deleted: number;
  monthly_savings: number;
  co2_saved_kg: number;
  cumulative_savings: number;
  cumulative_co2: number;
}

export interface ImpactTimeline {
  period: "day" | "week" | "month" | "year" | "all";
  data_points: TimelineDataPoint[];
  summary: Record<string, number>;
}

export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlocked: boolean;
  unlocked_at: string | null;
  progress: number; // 0-1
  threshold: number;
  current_value: number;
  category: "financial" | "environmental" | "engagement";
}

export interface UserAchievements {
  achievements: Achievement[];
  total_unlocked: number;
  total_available: number;
  completion_rate: number; // 0-1
}

export interface QuickStats {
  biggest_cleanup_monthly_cost: number;
  biggest_cleanup_resource_type: string | null;
  most_common_resource_type: string | null;
  most_common_resource_count: number;
  fastest_cleanup_hours: number | null;
  top_region: string | null;
  top_region_count: number;
  average_resource_age_days: number;
}
