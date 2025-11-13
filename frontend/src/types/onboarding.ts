/**
 * Onboarding types for CutCosts
 */

/**
 * Onboarding steps
 */
export enum OnboardingStep {
  WELCOME = "welcome",
  ADD_ACCOUNT = "add_account",
  RUN_SCAN = "run_scan",
  REVIEW_RESULTS = "review_results",
  COMPLETION = "completion",
}

/**
 * Onboarding progress state
 */
export interface OnboardingProgress {
  currentStep: OnboardingStep;
  completedSteps: OnboardingStep[];
  isCompleted: boolean;
  dismissed: boolean;
  accountAdded: boolean;
  firstScanCompleted: boolean;
  resultsReviewed: boolean;
}

/**
 * Checklist item
 */
export interface ChecklistItem {
  id: string;
  label: string;
  description?: string;
  completed: boolean;
  route?: string;
  icon?: React.ComponentType<{ className?: string }>;
}

/**
 * Onboarding wizard step configuration
 */
export interface OnboardingStepConfig {
  step: OnboardingStep;
  title: string;
  description: string;
  canSkip: boolean;
  canGoBack: boolean;
}

/**
 * Helper: Get all onboarding steps in order
 */
export function getAllSteps(): OnboardingStep[] {
  return [
    OnboardingStep.WELCOME,
    OnboardingStep.ADD_ACCOUNT,
    OnboardingStep.RUN_SCAN,
    OnboardingStep.REVIEW_RESULTS,
    OnboardingStep.COMPLETION,
  ];
}

/**
 * Helper: Get step number (1-indexed)
 */
export function getStepNumber(step: OnboardingStep): number {
  return getAllSteps().indexOf(step) + 1;
}

/**
 * Helper: Get next step
 */
export function getNextStep(currentStep: OnboardingStep): OnboardingStep | null {
  const steps = getAllSteps();
  const currentIndex = steps.indexOf(currentStep);

  if (currentIndex === -1 || currentIndex === steps.length - 1) {
    return null;
  }

  return steps[currentIndex + 1];
}

/**
 * Helper: Get previous step
 */
export function getPreviousStep(currentStep: OnboardingStep): OnboardingStep | null {
  const steps = getAllSteps();
  const currentIndex = steps.indexOf(currentStep);

  if (currentIndex <= 0) {
    return null;
  }

  return steps[currentIndex - 1];
}

/**
 * Helper: Calculate progress percentage
 */
export function calculateProgress(completedSteps: OnboardingStep[]): number {
  const totalSteps = getAllSteps().length;
  return Math.round((completedSteps.length / totalSteps) * 100);
}

/**
 * Helper: Check if step is completed
 */
export function isStepCompleted(
  step: OnboardingStep,
  completedSteps: OnboardingStep[]
): boolean {
  return completedSteps.includes(step);
}
