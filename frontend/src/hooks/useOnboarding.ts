/**
 * Custom hook for onboarding logic
 */

import { useRouter } from "next/navigation";
import { useOnboardingStore } from "@/stores/useOnboardingStore";
import {
  OnboardingStep,
  getStepNumber,
  calculateProgress,
  ChecklistItem,
} from "@/types/onboarding";
import { Cloud, Search, Eye, CheckCircle } from "lucide-react";

export function useOnboarding() {
  const store = useOnboardingStore();
  const router = useRouter();

  // Calculate progress percentage
  const progressPercentage = calculateProgress(store.completedSteps);

  // Get current step number (1-indexed)
  const currentStepNumber = getStepNumber(store.currentStep);

  // Total number of steps
  const totalSteps = 5;

  // Check if onboarding should be shown
  const shouldShowOnboarding = !store.isCompleted && !store.dismissed;

  // Navigation helpers
  const navigateToDashboard = () => {
    router.push("/dashboard");
  };

  const navigateToOnboarding = () => {
    router.push("/onboarding");
  };

  // Complete onboarding and go to dashboard
  const finishOnboarding = () => {
    store.completeOnboarding();
    navigateToDashboard();
  };

  // Skip onboarding and go to dashboard
  const skipOnboardingAndRedirect = () => {
    store.skipOnboarding();
    navigateToDashboard();
  };

  // Get checklist items
  const getChecklistItems = (): ChecklistItem[] => {
    return [
      {
        id: "account",
        label: "Connect cloud account",
        description: "Add your first AWS, Azure, or GCP account",
        completed: store.accountAdded,
        route: "/dashboard/accounts",
        icon: Cloud,
      },
      {
        id: "scan",
        label: "Run your first scan",
        description: "Detect orphaned resources in your cloud",
        completed: store.firstScanCompleted,
        route: "/dashboard/scans",
        icon: Search,
      },
      {
        id: "results",
        label: "Review results",
        description: "Check detected waste and potential savings",
        completed: store.resultsReviewed,
        route: "/dashboard/resources",
        icon: Eye,
      },
    ];
  };

  // Check if all checklist items are completed
  const isChecklistComplete = (): boolean => {
    return getChecklistItems().every((item) => item.completed);
  };

  return {
    // State
    currentStep: store.currentStep,
    completedSteps: store.completedSteps,
    isCompleted: store.isCompleted,
    dismissed: store.dismissed,
    accountAdded: store.accountAdded,
    firstScanCompleted: store.firstScanCompleted,
    resultsReviewed: store.resultsReviewed,

    // Computed
    progressPercentage,
    currentStepNumber,
    totalSteps,
    shouldShowOnboarding,
    checklistItems: getChecklistItems(),
    isChecklistComplete: isChecklistComplete(),

    // Actions
    setCurrentStep: store.setCurrentStep,
    goToNextStep: store.goToNextStep,
    goToPreviousStep: store.goToPreviousStep,
    completeStep: store.completeStep,
    completeOnboarding: store.completeOnboarding,
    skipOnboarding: store.skipOnboarding,
    resetOnboarding: store.resetOnboarding,
    setAccountAdded: store.setAccountAdded,
    setFirstScanCompleted: store.setFirstScanCompleted,
    setResultsReviewed: store.setResultsReviewed,

    // Navigation
    navigateToDashboard,
    navigateToOnboarding,
    finishOnboarding,
    skipOnboardingAndRedirect,
  };
}
