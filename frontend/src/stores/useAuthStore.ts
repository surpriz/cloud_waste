/**
 * Zustand store for authentication state
 */

import { create } from "zustand";
import { authAPI } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import type { User, LoginRequest, RegisterRequest } from "@/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  fetchCurrentUser: () => Promise<void>;
  clearError: () => void;
  resetStore: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

  login: async (data: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      await authAPI.login(data);
      const user = await authAPI.getCurrentUser();
      set({ user, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Login failed", isLoading: false });
      throw error;
    }
  },

  register: async (data: RegisterRequest) => {
    set({ isLoading: true, error: null });
    try {
      await authAPI.register(data);
      // Auto-login after registration
      await authAPI.login({
        username: data.email,
        password: data.password,
      });
      const user = await authAPI.getCurrentUser();
      set({ user, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Registration failed", isLoading: false });
      throw error;
    }
  },

  logout: () => {
    // Reset all Zustand stores to prevent memory pollution between users
    // This is CRITICAL - stores persist in RAM even after localStorage is cleared
    set({ user: null, error: null, isLoading: false });

    // Import stores dynamically to avoid circular dependencies
    import("./useAccountStore").then(({ useAccountStore }) => {
      useAccountStore.getState().resetStore();
    });
    import("./useScanStore").then(({ useScanStore }) => {
      useScanStore.getState().resetStore();
    });
    import("./useResourceStore").then(({ useResourceStore }) => {
      useResourceStore.getState().resetStore();
    });
    import("./useOnboardingStore").then(({ useOnboardingStore }) => {
      useOnboardingStore.getState().resetOnboarding();
    });

    // Call API logout and clear localStorage
    authAPI.logout();
    if (typeof window !== "undefined") {
      localStorage.clear();
      window.location.href = "/auth/login";
    }
  },

  fetchCurrentUser: async () => {
    if (!isAuthenticated()) {
      set({ user: null });
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const user = await authAPI.getCurrentUser();
      set({ user, isLoading: false });
    } catch (error: any) {
      set({ error: error.message, isLoading: false, user: null });
      // Call the store's own logout to handle cleanup
      useAuthStore.getState().logout();
    }
  },

  clearError: () => set({ error: null }),

  resetStore: () => {
    set({
      user: null,
      isLoading: false,
      error: null,
    });
  },
}));
