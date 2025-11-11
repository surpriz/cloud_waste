/**
 * Zustand store for onboarding state management
 */

import { create } from "zustand";
import { persist, StateStorage } from "zustand/middleware";
import {
  OnboardingStep,
  OnboardingProgress,
  getAllSteps,
  getNextStep,
  getPreviousStep,
} from "@/types/onboarding";
import { decodeToken } from "@/lib/auth";

interface OnboardingState extends OnboardingProgress {
  // Actions
  setCurrentStep: (step: OnboardingStep) => void;
  goToNextStep: () => void;
  goToPreviousStep: () => void;
  completeStep: (step: OnboardingStep) => void;
  completeOnboarding: () => void;
  skipOnboarding: () => void;
  resetOnboarding: () => void;
  setAccountAdded: (added: boolean) => void;
  setFirstScanCompleted: (completed: boolean) => void;
  setResultsReviewed: (reviewed: boolean) => void;
}

/**
 * Get current user ID from JWT token
 */
function getUserId(): string | null {
  if (typeof window === "undefined") return null;

  const token = localStorage.getItem("access_token");
  if (!token) return null;

  try {
    const decoded = decodeToken(token);
    // JWT tokens typically have 'sub' (subject) or 'user_id' field
    return decoded?.sub || decoded?.user_id || null;
  } catch {
    return null;
  }
}

/**
 * Create user-scoped storage that isolates localStorage by user ID
 * This prevents state pollution when multiple users use the same browser
 */
const createUserScopedStorage = (baseKey: string): StateStorage => {
  return {
    getItem: (name: string) => {
      const userId = getUserId();
      const key = userId ? `${baseKey}-${userId}` : baseKey;
      const value = localStorage.getItem(key);
      return value;
    },
    setItem: (name: string, value: string) => {
      const userId = getUserId();
      const key = userId ? `${baseKey}-${userId}` : baseKey;
      localStorage.setItem(key, value);
    },
    removeItem: (name: string) => {
      const userId = getUserId();
      const key = userId ? `${baseKey}-${userId}` : baseKey;
      localStorage.removeItem(key);
    },
  };
};

const initialState: OnboardingProgress = {
  currentStep: OnboardingStep.WELCOME,
  completedSteps: [],
  isCompleted: false,
  dismissed: false,
  accountAdded: false,
  firstScanCompleted: false,
  resultsReviewed: false,
};

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      ...initialState,

      setCurrentStep: (step: OnboardingStep) => {
        set({ currentStep: step });
      },

      goToNextStep: () => {
        const currentStep = get().currentStep;
        const nextStep = getNextStep(currentStep);

        if (nextStep) {
          // Mark current step as completed
          const completedSteps = get().completedSteps;
          if (!completedSteps.includes(currentStep)) {
            set({
              completedSteps: [...completedSteps, currentStep],
            });
          }

          // Move to next step
          set({ currentStep: nextStep });
        }
      },

      goToPreviousStep: () => {
        const currentStep = get().currentStep;
        const previousStep = getPreviousStep(currentStep);

        if (previousStep) {
          set({ currentStep: previousStep });
        }
      },

      completeStep: (step: OnboardingStep) => {
        const completedSteps = get().completedSteps;

        if (!completedSteps.includes(step)) {
          set({
            completedSteps: [...completedSteps, step],
          });
        }
      },

      completeOnboarding: () => {
        set({
          isCompleted: true,
          completedSteps: getAllSteps(),
          currentStep: OnboardingStep.COMPLETION,
        });
      },

      skipOnboarding: () => {
        set({
          dismissed: true,
        });
      },

      resetOnboarding: () => {
        set(initialState);
      },

      setAccountAdded: (added: boolean) => {
        set({ accountAdded: added });

        if (added) {
          get().completeStep(OnboardingStep.ADD_ACCOUNT);
        }
      },

      setFirstScanCompleted: (completed: boolean) => {
        set({ firstScanCompleted: completed });

        if (completed) {
          get().completeStep(OnboardingStep.RUN_SCAN);
        }
      },

      setResultsReviewed: (reviewed: boolean) => {
        set({ resultsReviewed: reviewed });

        if (reviewed) {
          get().completeStep(OnboardingStep.REVIEW_RESULTS);
        }
      },
    }),
    {
      name: "cloudwaste-onboarding", // Base key (will be scoped by user ID)
      storage: createUserScopedStorage("cloudwaste-onboarding"),
      version: 1,
    }
  )
);
