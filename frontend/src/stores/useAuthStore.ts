/**
 * Zustand store for authentication state
 */

import { create } from "zustand";
import { authAPI } from "@/lib/api";
import { isAuthenticated, logout as authLogout } from "@/lib/auth";
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
    authLogout();
    set({ user: null, error: null });
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
      authLogout();
    }
  },

  clearError: () => set({ error: null }),
}));
