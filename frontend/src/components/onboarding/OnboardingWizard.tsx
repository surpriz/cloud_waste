"use client";

import { X, ArrowLeft, ArrowRight } from "lucide-react";
import { OnboardingStep } from "@/types/onboarding";
import { useOnboarding } from "@/hooks/useOnboarding";
import { ProgressBar } from "./ProgressBar";
import { WelcomeStep } from "./WelcomeStep";
import { AddAccountStep } from "./AddAccountStep";
import { RunScanStep } from "./RunScanStep";
import { ReviewResultsStep } from "./ReviewResultsStep";
import { CompletionStep } from "./CompletionStep";

/**
 * Onboarding Wizard Container
 *
 * Manages navigation and state for all onboarding steps
 */
export function OnboardingWizard() {
  const {
    currentStep,
    currentStepNumber,
    totalSteps,
    goToNextStep,
    goToPreviousStep,
    skipOnboardingAndRedirect,
    finishOnboarding,
    setResultsReviewed,
  } = useOnboarding();

  const stepTitles = ["Welcome", "Account", "Scan", "Review", "Complete"];

  const canGoBack =
    currentStep !== OnboardingStep.WELCOME &&
    currentStep !== OnboardingStep.COMPLETION;

  const canSkip = currentStep !== OnboardingStep.COMPLETION;

  // Handle next step
  const handleNext = () => {
    // Mark review as done when leaving review step
    if (currentStep === OnboardingStep.REVIEW_RESULTS) {
      setResultsReviewed(true);
    }

    goToNextStep();
  };

  // Render current step component
  const renderStep = () => {
    switch (currentStep) {
      case OnboardingStep.WELCOME:
        return <WelcomeStep onNext={handleNext} />;

      case OnboardingStep.ADD_ACCOUNT:
        return (
          <AddAccountStep onNext={handleNext} onSkip={handleNext} />
        );

      case OnboardingStep.RUN_SCAN:
        return (
          <RunScanStep onNext={handleNext} onBack={goToPreviousStep} />
        );

      case OnboardingStep.REVIEW_RESULTS:
        return <ReviewResultsStep onNext={handleNext} />;

      case OnboardingStep.COMPLETION:
        return <CompletionStep onFinish={finishOnboarding} />;

      default:
        return <WelcomeStep onNext={handleNext} />;
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      {/* Decorative background */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute top-0 left-0 h-96 w-96 rounded-full bg-blue-300 blur-3xl animate-pulse"></div>
        <div className="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-purple-300 blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Skip button */}
      {canSkip && (
        <button
          onClick={skipOnboardingAndRedirect}
          className="absolute top-6 right-6 z-50 inline-flex items-center gap-2 rounded-xl border-2 border-gray-300 bg-white/80 backdrop-blur-sm px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-white transition-all"
        >
          <X className="h-4 w-4" />
          Skip Tutorial
        </button>
      )}

      {/* Main content */}
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-12">
        {/* Progress bar */}
        {currentStep !== OnboardingStep.COMPLETION && (
          <ProgressBar
            currentStep={currentStepNumber}
            totalSteps={totalSteps}
            stepTitles={stepTitles}
          />
        )}

        {/* Step content */}
        <div className="w-full max-w-5xl">
          <div className="rounded-3xl border border-gray-200/50 bg-white/70 backdrop-blur-xl p-8 md:p-12 shadow-2xl">
            {renderStep()}
          </div>
        </div>

        {/* Navigation buttons (not shown on completion) */}
        {currentStep !== OnboardingStep.COMPLETION &&
          currentStep !== OnboardingStep.WELCOME && (
            <div className="mt-8 flex items-center gap-4">
              {canGoBack && (
                <button
                  onClick={goToPreviousStep}
                  className="inline-flex items-center gap-2 rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <ArrowLeft className="h-5 w-5" />
                  Back
                </button>
              )}
            </div>
          )}

        {/* Progress indicator text */}
        {currentStep !== OnboardingStep.COMPLETION && (
          <p className="mt-6 text-sm text-gray-600">
            Step {currentStepNumber} of {totalSteps}
          </p>
        )}
      </div>
    </div>
  );
}
