import { Check } from "lucide-react";

interface ProgressBarProps {
  currentStep: number;
  totalSteps: number;
  stepTitles?: string[];
}

/**
 * Progress Bar Component
 *
 * Shows visual progress through onboarding steps with numbered circles
 */
export function ProgressBar({
  currentStep,
  totalSteps,
  stepTitles = [],
}: ProgressBarProps) {
  const progressPercentage = ((currentStep - 1) / (totalSteps - 1)) * 100;

  return (
    <div className="w-full max-w-3xl mx-auto mb-8">
      {/* Progress line */}
      <div className="relative">
        <div className="absolute top-5 left-0 h-1 w-full bg-gray-200 rounded-full"></div>
        <div
          className="absolute top-5 left-0 h-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full transition-all duration-500"
          style={{ width: `${progressPercentage}%` }}
        ></div>

        {/* Step circles */}
        <div className="relative flex justify-between">
          {Array.from({ length: totalSteps }).map((_, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === currentStep;
            const isCompleted = stepNumber < currentStep;
            const hasTitle = stepTitles[index];

            return (
              <div key={stepNumber} className="flex flex-col items-center">
                {/* Circle */}
                <div
                  className={`
                    flex h-10 w-10 items-center justify-center rounded-full border-4
                    transition-all duration-300 z-10
                    ${
                      isCompleted
                        ? "bg-gradient-to-br from-blue-600 to-purple-600 border-white shadow-lg"
                        : isActive
                        ? "bg-white border-blue-600 shadow-lg scale-110"
                        : "bg-white border-gray-300"
                    }
                  `}
                >
                  {isCompleted ? (
                    <Check className="h-5 w-5 text-white" />
                  ) : (
                    <span
                      className={`text-sm font-bold ${
                        isActive ? "text-blue-600" : "text-gray-400"
                      }`}
                    >
                      {stepNumber}
                    </span>
                  )}
                </div>

                {/* Step title (optional) */}
                {hasTitle && (
                  <span
                    className={`mt-2 text-xs font-medium text-center transition-colors ${
                      isActive
                        ? "text-blue-600"
                        : isCompleted
                        ? "text-gray-700"
                        : "text-gray-400"
                    }`}
                  >
                    {stepTitles[index]}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Step indicator text */}
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-600">
          Step <span className="font-bold text-blue-600">{currentStep}</span> of{" "}
          <span className="font-bold">{totalSteps}</span>
        </p>
      </div>
    </div>
  );
}
