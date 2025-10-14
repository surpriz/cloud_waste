import { create } from "zustand";
import { impactAPI } from "@/lib/api";
import type {
  ImpactSummary,
  ImpactTimeline,
  UserAchievements,
  QuickStats,
} from "@/types/impact";

interface ImpactStore {
  // State
  summary: ImpactSummary | null;
  timeline: ImpactTimeline | null;
  achievements: UserAchievements | null;
  quickStats: QuickStats | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchSummary: () => Promise<void>;
  fetchTimeline: (period: "day" | "week" | "month" | "year" | "all") => Promise<void>;
  fetchAchievements: () => Promise<void>;
  fetchQuickStats: () => Promise<void>;
  fetchAll: (period?: "day" | "week" | "month" | "year" | "all") => Promise<void>;
  clearError: () => void;
}

export const useImpactStore = create<ImpactStore>((set) => ({
  // Initial state
  summary: null,
  timeline: null,
  achievements: null,
  quickStats: null,
  isLoading: false,
  error: null,

  // Fetch impact summary
  fetchSummary: async () => {
    set({ isLoading: true, error: null });
    try {
      const summary = await impactAPI.getSummary();
      set({ summary, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.message || "Failed to fetch impact summary";
      set({ error: errorMsg, isLoading: false });
      console.error("Error fetching impact summary:", err);
    }
  },

  // Fetch impact timeline
  fetchTimeline: async (period = "month") => {
    set({ isLoading: true, error: null });
    try {
      const timeline = await impactAPI.getTimeline(period);
      set({ timeline, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.message || "Failed to fetch impact timeline";
      set({ error: errorMsg, isLoading: false });
      console.error("Error fetching impact timeline:", err);
    }
  },

  // Fetch user achievements
  fetchAchievements: async () => {
    set({ isLoading: true, error: null });
    try {
      const achievements = await impactAPI.getAchievements();
      set({ achievements, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.message || "Failed to fetch achievements";
      set({ error: errorMsg, isLoading: false });
      console.error("Error fetching achievements:", err);
    }
  },

  // Fetch quick stats
  fetchQuickStats: async () => {
    set({ isLoading: true, error: null });
    try {
      const quickStats = await impactAPI.getQuickStats();
      set({ quickStats, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.message || "Failed to fetch quick stats";
      set({ error: errorMsg, isLoading: false });
      console.error("Error fetching quick stats:", err);
    }
  },

  // Fetch all impact data at once
  fetchAll: async (period = "month") => {
    set({ isLoading: true, error: null });
    try {
      const [summary, timeline, achievements, quickStats] = await Promise.all([
        impactAPI.getSummary(),
        impactAPI.getTimeline(period),
        impactAPI.getAchievements(),
        impactAPI.getQuickStats(),
      ]);

      set({
        summary,
        timeline,
        achievements,
        quickStats,
        isLoading: false,
      });
    } catch (err: any) {
      const errorMsg = err.message || "Failed to fetch impact data";
      set({ error: errorMsg, isLoading: false });
      console.error("Error fetching impact data:", err);
    }
  },

  // Clear error
  clearError: () => set({ error: null }),
}));
