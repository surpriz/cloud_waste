/**
 * Zustand store for scans
 */

import { create } from "zustand";
import { scansAPI } from "@/lib/api";
import type { Scan, ScanCreate, ScanWithResources, ScanSummary } from "@/types";
import { useOnboardingStore } from "./useOnboardingStore";

interface ScanState {
  scans: Scan[];
  selectedScan: ScanWithResources | null;
  summary: ScanSummary | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchScans: () => Promise<void>;
  fetchScan: (id: string) => Promise<void>;
  createScan: (data: ScanCreate) => Promise<Scan>;
  deleteScan: (id: string) => Promise<void>;
  deleteAllScans: () => Promise<void>;
  fetchSummary: (cloudAccountId?: string) => Promise<void>;
  fetchScansByAccount: (accountId: string) => Promise<void>;
  clearError: () => void;
  resetStore: () => void;
}

export const useScanStore = create<ScanState>((set) => ({
  scans: [],
  selectedScan: null,
  summary: null,
  isLoading: false,
  error: null,

  fetchScans: async () => {
    set({ isLoading: true, error: null });
    try {
      const scans = await scansAPI.list();
      set({ scans, isLoading: false });

      // Notify onboarding if user has completed scans
      const hasCompletedScans = scans.some((scan) => scan.status === "completed");
      if (hasCompletedScans) {
        useOnboardingStore.getState().setFirstScanCompleted(true);
      }
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch scans", isLoading: false });
    }
  },

  fetchScan: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const scan = await scansAPI.get(id);
      set({ selectedScan: scan, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch scan", isLoading: false });
    }
  },

  createScan: async (data: ScanCreate) => {
    set({ isLoading: true, error: null });
    try {
      const scan = await scansAPI.create(data);
      set((state) => ({
        scans: [scan, ...state.scans],
        isLoading: false,
      }));

      // Notify onboarding if scan is completed
      if (scan.status === "completed") {
        useOnboardingStore.getState().setFirstScanCompleted(true);
      }

      return scan;
    } catch (error: any) {
      set({ error: error.message || "Failed to create scan", isLoading: false });
      throw error;
    }
  },

  fetchSummary: async (cloudAccountId?: string) => {
    set({ isLoading: true, error: null });
    try {
      const summary = await scansAPI.getSummary(cloudAccountId);
      set({ summary, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch summary", isLoading: false });
    }
  },

  fetchScansByAccount: async (accountId: string) => {
    set({ isLoading: true, error: null });
    try {
      const scans = await scansAPI.listByAccount(accountId);
      set({ scans, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch scans", isLoading: false });
    }
  },

  deleteScan: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await scansAPI.delete(id);
      set((state) => ({
        scans: state.scans.filter((s) => s.id !== id),
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to delete scan", isLoading: false });
      throw error;
    }
  },

  deleteAllScans: async () => {
    set({ isLoading: true, error: null });
    try {
      await scansAPI.deleteAll();
      set({
        scans: [],
        isLoading: false,
      });
    } catch (error: any) {
      set({ error: error.message || "Failed to delete all scans", isLoading: false });
      throw error;
    }
  },

  clearError: () => set({ error: null }),

  resetStore: () => {
    set({
      scans: [],
      selectedScan: null,
      summary: null,
      isLoading: false,
      error: null,
    });
  },
}));
