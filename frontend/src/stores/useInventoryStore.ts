/**
 * Zustand store for Cost Intelligence (Inventory)
 */

import { create } from "zustand";
import type {
  AllCloudResource,
  InventoryStats,
  CostBreakdown,
  HighCostResource,
  InventoryFilters,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// API client for inventory endpoints
const inventoryAPI = {
  getStats: async (cloudAccountId: string): Promise<InventoryStats> => {
    const response = await fetch(
      `${API_URL}/api/v1/inventory/stats?cloud_account_id=${cloudAccountId}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      }
    );
    if (!response.ok) throw new Error("Failed to fetch inventory stats");
    return response.json();
  },

  getCostBreakdown: async (cloudAccountId: string): Promise<CostBreakdown> => {
    const response = await fetch(
      `${API_URL}/api/v1/inventory/cost-breakdown?cloud_account_id=${cloudAccountId}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      }
    );
    if (!response.ok) throw new Error("Failed to fetch cost breakdown");
    return response.json();
  },

  getHighCostResources: async (
    cloudAccountId: string,
    minCost: number = 100,
    limit: number = 10
  ): Promise<HighCostResource[]> => {
    const response = await fetch(
      `${API_URL}/api/v1/inventory/high-cost-resources?cloud_account_id=${cloudAccountId}&min_cost=${minCost}&limit=${limit}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      }
    );
    if (!response.ok) throw new Error("Failed to fetch high-cost resources");
    return response.json();
  },

  getOptimizableResources: async (
    cloudAccountId: string,
    limit: number = 100
  ): Promise<AllCloudResource[]> => {
    const response = await fetch(
      `${API_URL}/api/v1/inventory/optimizable-resources?cloud_account_id=${cloudAccountId}&limit=${limit}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      }
    );
    if (!response.ok) throw new Error("Failed to fetch optimizable resources");
    return response.json();
  },

  getAllResources: async (
    filters: InventoryFilters
  ): Promise<AllCloudResource[]> => {
    const params = new URLSearchParams();
    if (filters.cloud_account_id)
      params.append("cloud_account_id", filters.cloud_account_id);
    if (filters.resource_type)
      params.append("resource_type", filters.resource_type);
    if (filters.is_optimizable !== undefined)
      params.append("is_optimizable", String(filters.is_optimizable));
    if (filters.min_cost !== undefined)
      params.append("min_cost", String(filters.min_cost));
    if (filters.skip !== undefined) params.append("skip", String(filters.skip));
    if (filters.limit !== undefined)
      params.append("limit", String(filters.limit));

    const response = await fetch(`${API_URL}/api/v1/inventory/resources?${params}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
    });
    if (!response.ok) throw new Error("Failed to fetch all resources");
    return response.json();
  },

  getResourceDetails: async (resourceId: string): Promise<AllCloudResource> => {
    const response = await fetch(`${API_URL}/api/v1/inventory/resources/${resourceId}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
    });
    if (!response.ok) throw new Error("Failed to fetch resource details");
    return response.json();
  },

  runInventoryScan: async (cloudAccountId: string): Promise<{ scan_id: string }> => {
    const response = await fetch(`${API_URL}/api/v1/scans/inventory`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
      body: JSON.stringify({ cloud_account_id: cloudAccountId }),
    });
    if (!response.ok) throw new Error("Failed to start inventory scan");
    return response.json();
  },
};

interface InventoryState {
  stats: InventoryStats | null;
  costBreakdown: CostBreakdown | null;
  highCostResources: HighCostResource[];
  optimizableResources: AllCloudResource[];
  allResources: AllCloudResource[];
  selectedResource: AllCloudResource | null;
  filters: InventoryFilters;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchStats: (cloudAccountId: string) => Promise<void>;
  fetchCostBreakdown: (cloudAccountId: string) => Promise<void>;
  fetchHighCostResources: (
    cloudAccountId: string,
    minCost?: number,
    limit?: number
  ) => Promise<void>;
  fetchOptimizableResources: (
    cloudAccountId: string,
    limit?: number
  ) => Promise<void>;
  fetchAllResources: (filters: InventoryFilters) => Promise<void>;
  fetchResourceDetails: (resourceId: string) => Promise<void>;
  runInventoryScan: (cloudAccountId: string) => Promise<void>;
  setFilters: (filters: InventoryFilters) => void;
  clearFilters: () => void;
  clearError: () => void;
  resetStore: () => void;
}

export const useInventoryStore = create<InventoryState>((set, get) => ({
  stats: null,
  costBreakdown: null,
  highCostResources: [],
  optimizableResources: [],
  allResources: [],
  selectedResource: null,
  filters: {},
  isLoading: false,
  error: null,

  fetchStats: async (cloudAccountId: string) => {
    set({ isLoading: true, error: null });
    try {
      const stats = await inventoryAPI.getStats(cloudAccountId);
      set({ stats, isLoading: false });
    } catch (error: any) {
      set({
        error: error.message || "Failed to fetch inventory stats",
        isLoading: false,
      });
    }
  },

  fetchCostBreakdown: async (cloudAccountId: string) => {
    set({ isLoading: true, error: null });
    try {
      const costBreakdown = await inventoryAPI.getCostBreakdown(cloudAccountId);
      set({ costBreakdown, isLoading: false });
    } catch (error: any) {
      set({
        error: error.message || "Failed to fetch cost breakdown",
        isLoading: false,
      });
    }
  },

  fetchHighCostResources: async (
    cloudAccountId: string,
    minCost: number = 100,
    limit: number = 10
  ) => {
    set({ isLoading: true, error: null });
    try {
      const highCostResources = await inventoryAPI.getHighCostResources(
        cloudAccountId,
        minCost,
        limit
      );
      set({ highCostResources, isLoading: false });
    } catch (error: any) {
      set({
        error: error.message || "Failed to fetch high-cost resources",
        isLoading: false,
      });
    }
  },

  fetchOptimizableResources: async (
    cloudAccountId: string,
    limit: number = 100
  ) => {
    set({ isLoading: true, error: null });
    try {
      const optimizableResources =
        await inventoryAPI.getOptimizableResources(cloudAccountId, limit);
      set({ optimizableResources, isLoading: false });
    } catch (error: any) {
      set({
        error: error.message || "Failed to fetch optimizable resources",
        isLoading: false,
      });
    }
  },

  fetchAllResources: async (filters: InventoryFilters) => {
    set({ isLoading: true, error: null });
    try {
      const allResources = await inventoryAPI.getAllResources(filters);
      set({ allResources, filters, isLoading: false });
    } catch (error: any) {
      set({
        error: error.message || "Failed to fetch all resources",
        isLoading: false,
      });
    }
  },

  fetchResourceDetails: async (resourceId: string) => {
    set({ isLoading: true, error: null });
    try {
      const selectedResource =
        await inventoryAPI.getResourceDetails(resourceId);
      set({ selectedResource, isLoading: false });
    } catch (error: any) {
      set({
        error: error.message || "Failed to fetch resource details",
        isLoading: false,
      });
    }
  },

  runInventoryScan: async (cloudAccountId: string) => {
    set({ isLoading: true, error: null });
    try {
      await inventoryAPI.runInventoryScan(cloudAccountId);
      set({ isLoading: false });
      // Success - inventory scan started in background
    } catch (error: any) {
      set({
        error: error.message || "Failed to start inventory scan",
        isLoading: false,
      });
    }
  },

  setFilters: (filters: InventoryFilters) => {
    set({ filters });
  },

  clearFilters: () => {
    set({ filters: {} });
  },

  clearError: () => {
    set({ error: null });
  },

  resetStore: () => {
    set({
      stats: null,
      costBreakdown: null,
      highCostResources: [],
      optimizableResources: [],
      allResources: [],
      selectedResource: null,
      filters: {},
      isLoading: false,
      error: null,
    });
  },
}));
