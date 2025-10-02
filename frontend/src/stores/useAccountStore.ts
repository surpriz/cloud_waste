/**
 * Zustand store for cloud accounts
 */

import { create } from "zustand";
import { accountsAPI } from "@/lib/api";
import type { CloudAccount, CloudAccountCreate } from "@/types";

interface AccountState {
  accounts: CloudAccount[];
  selectedAccount: CloudAccount | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchAccounts: () => Promise<void>;
  createAccount: (data: CloudAccountCreate) => Promise<CloudAccount>;
  updateAccount: (id: string, data: Partial<CloudAccountCreate>) => Promise<void>;
  deleteAccount: (id: string) => Promise<void>;
  selectAccount: (account: CloudAccount | null) => void;
  validateAccount: (id: string) => Promise<any>;
  clearError: () => void;
}

export const useAccountStore = create<AccountState>((set, get) => ({
  accounts: [],
  selectedAccount: null,
  isLoading: false,
  error: null,

  fetchAccounts: async () => {
    set({ isLoading: true, error: null });
    try {
      const accounts = await accountsAPI.list();
      set({ accounts, isLoading: false });
    } catch (error: any) {
      set({ error: error.message || "Failed to fetch accounts", isLoading: false });
    }
  },

  createAccount: async (data: CloudAccountCreate) => {
    set({ isLoading: true, error: null });
    try {
      const account = await accountsAPI.create(data);
      set((state) => ({
        accounts: [...state.accounts, account],
        isLoading: false,
      }));
      return account;
    } catch (error: any) {
      set({ error: error.message || "Failed to create account", isLoading: false });
      throw error;
    }
  },

  updateAccount: async (id: string, data: Partial<CloudAccountCreate>) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await accountsAPI.update(id, data);
      set((state) => ({
        accounts: state.accounts.map((acc) =>
          acc.id === id ? updated : acc
        ),
        selectedAccount:
          state.selectedAccount?.id === id ? updated : state.selectedAccount,
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to update account", isLoading: false });
      throw error;
    }
  },

  deleteAccount: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await accountsAPI.delete(id);
      set((state) => ({
        accounts: state.accounts.filter((acc) => acc.id !== id),
        selectedAccount:
          state.selectedAccount?.id === id ? null : state.selectedAccount,
        isLoading: false,
      }));
    } catch (error: any) {
      set({ error: error.message || "Failed to delete account", isLoading: false });
      throw error;
    }
  },

  selectAccount: (account: CloudAccount | null) => {
    set({ selectedAccount: account });
  },

  validateAccount: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const result = await accountsAPI.validate(id);
      set({ isLoading: false });
      return result;
    } catch (error: any) {
      set({ error: error.message || "Account validation failed", isLoading: false });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
}));
