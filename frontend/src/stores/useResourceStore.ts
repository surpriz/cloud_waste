/**
 * Zustand store for orphan resources
 */

import { create } from "zustand";
import { resourcesAPI } from "@/lib/api";
import type {
  OrphanResource,
  OrphanResourceUpdate,
  OrphanResourceStats,
  ResourceFilters,
} from "@/types";

interface ResourceState {
  resources: OrphanResource[];
  selectedResource: OrphanResource | null;
  stats: OrphanResourceStats | null;
  topCostResources: OrphanResource[];
  filters: ResourceFilters;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchResources: (filters?: ResourceFilters) => Promise<void>;
  fetchResource: (id: string) => Promise<void>;
  updateResource: (id: string, data: OrphanResourceUpdate) => Promise<void>;
  deleteResource: (id: string) => Promise<void>;
  fetchStats: (cloudAccountId?: string, status?: string) => Promise<void>;
  fetchTopCost: (cloudAccountId?: string, limit?: number) => Promise<void>;
  setFilters: (filters: ResourceFilters) => void;
  clearFilters: () => void;
  clearError: () => void;
}

export const useResourceStore = create<ResourceState>((set, get) => ({
  resources: [],
  selectedResource: null,
  stats: null,
  topCostResources: [],
  filters: {},
  isLoading: false,
  error: null,

  fetchResources: async (filters?: ResourceFilters) => {
    set({ isLoading: true, error: null });
    const activeFilters = filters || get().filters;
    try {
      const resources = await resourcesAPI.list(activeFilters);
      set({ resources, filters: activeFilters, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch resources", isLoading: false });
    }
  },

  fetchResource: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const resource = await resourcesAPI.get(id);
      set({ selectedResource: resource, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch resource", isLoading: false });
    }
  },

  updateResource: async (id: string, data: OrphanResourceUpdate) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await resourcesAPI.update(id, data);
      set((state) => ({
        resources: state.resources.map((res) =>
          res.id === id ? updated : res
        ),
        selectedResource:
          state.selectedResource?.id === id ? updated : state.selectedResource,
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to update resource", isLoading: false });
      throw error;
    }
  },

  deleteResource: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await resourcesAPI.delete(id);
      set((state) => ({
        resources: state.resources.filter((res) => res.id !== id),
        selectedResource:
          state.selectedResource?.id === id ? null : state.selectedResource,
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to delete resource", isLoading: false });
      throw error;
    }
  },

  fetchStats: async (cloudAccountId?: string, status?: string) => {
    set({ isLoading: true, error: null });
    try {
      const stats = await resourcesAPI.getStats(cloudAccountId, status);
      set({ stats, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch stats", isLoading: false });
    }
  },

  fetchTopCost: async (cloudAccountId?: string, limit: number = 10) => {
    set({ isLoading: true, error: null });
    try {
      const topCostResources = await resourcesAPI.getTopCost(cloudAccountId, limit);
      set({ topCostResources, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch top cost resources", isLoading: false });
    }
  },

  setFilters: (filters: ResourceFilters) => {
    set({ filters });
  },

  clearFilters: () => {
    set({ filters: {} });
  },

  clearError: () => set({ error: null }),
}));
