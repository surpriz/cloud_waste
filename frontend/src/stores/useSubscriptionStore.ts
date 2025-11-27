/**
 * Subscription store for managing user subscription state
 */

import { create } from "zustand";
import api from "@/lib/api";
import type {
  SubscriptionPlan,
  UserSubscription,
} from "@/types/subscription";

interface SubscriptionState {
  // Data
  plans: SubscriptionPlan[];
  currentSubscription: UserSubscription | null;

  // Loading states
  isLoadingPlans: boolean;
  isLoadingSubscription: boolean;
  isCreatingCheckout: boolean;

  // Error states
  plansError: string | null;
  subscriptionError: string | null;
  checkoutError: string | null;

  // Actions
  fetchPlans: () => Promise<void>;
  fetchCurrentSubscription: () => Promise<void>;
  createCheckoutSession: (
    planName: "pro" | "enterprise",
    successUrl: string,
    cancelUrl: string
  ) => Promise<void>;
  openCustomerPortal: (returnUrl: string) => Promise<void>;
  clearErrors: () => void;
  reset: () => void;

  // Helper methods
  canScan: () => boolean;
  canAddCloudAccount: () => boolean;
  hasFeature: (
    feature:
      | "ai_chat"
      | "impact_tracking"
      | "email_notifications"
      | "api_access"
      | "priority_support"
  ) => boolean;
  getScanUsage: () => { used: number; limit: number | null };
}

const useSubscriptionStore = create<SubscriptionState>((set, get) => ({
  // Initial state
  plans: [],
  currentSubscription: null,
  isLoadingPlans: false,
  isLoadingSubscription: false,
  isCreatingCheckout: false,
  plansError: null,
  subscriptionError: null,
  checkoutError: null,

  // Fetch all available plans
  fetchPlans: async () => {
    set({ isLoadingPlans: true, plansError: null });
    try {
      const plans = await api.getSubscriptionPlans();
      set({ plans, isLoadingPlans: false });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to fetch plans";
      set({ plansError: message, isLoadingPlans: false });
    }
  },

  // Fetch current user subscription
  fetchCurrentSubscription: async () => {
    set({ isLoadingSubscription: true, subscriptionError: null });
    try {
      const subscription = await api.getCurrentSubscription();
      set({ currentSubscription: subscription, isLoadingSubscription: false });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to fetch subscription";
      set({ subscriptionError: message, isLoadingSubscription: false });
    }
  },

  // Create Stripe Checkout Session and redirect
  createCheckoutSession: async (planName, successUrl, cancelUrl) => {
    set({ isCreatingCheckout: true, checkoutError: null });
    try {
      const session = await api.createCheckoutSession({
        plan_name: planName,
        success_url: successUrl,
        cancel_url: cancelUrl,
      });

      // Redirect to Stripe Checkout
      window.location.href = session.url;
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to create checkout session";
      set({ checkoutError: message, isCreatingCheckout: false });
      throw error;
    }
  },

  // Open Stripe Customer Portal
  openCustomerPortal: async (returnUrl) => {
    try {
      const session = await api.createPortalSession({ return_url: returnUrl });
      window.location.href = session.url;
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to open customer portal";
      set({ subscriptionError: message });
      throw error;
    }
  },

  // Clear all errors
  clearErrors: () => {
    set({
      plansError: null,
      subscriptionError: null,
      checkoutError: null,
    });
  },

  // Reset store
  reset: () => {
    set({
      plans: [],
      currentSubscription: null,
      isLoadingPlans: false,
      isLoadingSubscription: false,
      isCreatingCheckout: false,
      plansError: null,
      subscriptionError: null,
      checkoutError: null,
    });
  },

  // Helper: Check if user can perform a scan
  canScan: () => {
    const { currentSubscription } = get();
    if (!currentSubscription) return false;

    const { plan, scans_used_this_month } = currentSubscription;

    // Unlimited scans
    if (plan.max_scans_per_month === null) return true;

    // Check if under limit
    return scans_used_this_month < plan.max_scans_per_month;
  },

  // Helper: Check if user can add cloud account
  canAddCloudAccount: () => {
    const { currentSubscription } = get();
    if (!currentSubscription) return false;

    const { plan } = currentSubscription;

    // Unlimited accounts
    if (plan.max_cloud_accounts === null) return true;

    // Note: This would need to check actual account count
    // For now, just return true if plan allows accounts
    return true;
  },

  // Helper: Check if user has access to a feature
  hasFeature: (feature) => {
    const { currentSubscription } = get();
    if (!currentSubscription) return false;

    const { plan } = currentSubscription;

    switch (feature) {
      case "ai_chat":
        return plan.has_ai_chat;
      case "impact_tracking":
        return plan.has_impact_tracking;
      case "email_notifications":
        return plan.has_email_notifications;
      case "api_access":
        return plan.has_api_access;
      case "priority_support":
        return plan.has_priority_support;
      default:
        return false;
    }
  },

  // Helper: Get scan usage stats
  getScanUsage: () => {
    const { currentSubscription } = get();
    if (!currentSubscription) {
      return { used: 0, limit: null };
    }

    return {
      used: currentSubscription.scans_used_this_month,
      limit: currentSubscription.plan.max_scans_per_month,
    };
  },
}));

export default useSubscriptionStore;
