import { AlertCircle, RefreshCw } from "lucide-react";
import { ErrorAction } from "@/types/errors";

interface ErrorStateProps {
  title?: string;
  message: string;
  action?: ErrorAction;
  showIcon?: boolean;
}

/**
 * Error State Component
 *
 * Displays an error message with optional retry action.
 * Used for API errors, validation errors, and other error states.
 *
 * @example
 * ```tsx
 * <ErrorState
 *   title="Échec de chargement"
 *   message="Impossible de charger les comptes cloud"
 *   action={{
 *     label: "Réessayer",
 *     onClick: () => refetch(),
 *     variant: "primary",
 *     icon: RefreshCw
 *   }}
 * />
 * ```
 */
export function ErrorState({
  title = "Une erreur est survenue",
  message,
  action,
  showIcon = true,
}: ErrorStateProps) {
  const Icon = action?.icon;

  return (
    <div className="flex min-h-[300px] flex-col items-center justify-center rounded-lg border border-red-200 bg-red-50/50 p-8 text-center">
      {showIcon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
          <AlertCircle className="h-6 w-6 text-red-600" />
        </div>
      )}

      <h3 className="mb-2 text-lg font-semibold text-gray-900">{title}</h3>

      <p className="mb-6 max-w-md text-sm text-gray-600">{message}</p>

      {action && (
        <button
          onClick={action.onClick}
          className={getButtonClasses(action.variant)}
        >
          {Icon && <Icon className="h-4 w-4" />}
          {action.label}
        </button>
      )}
    </div>
  );
}

function getButtonClasses(variant: ErrorAction["variant"] = "primary"): string {
  const baseClasses =
    "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";

  switch (variant) {
    case "primary":
      return `${baseClasses} bg-red-600 text-white hover:bg-red-700 focus:ring-red-500`;
    case "secondary":
      return `${baseClasses} bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500`;
    case "outline":
      return `${baseClasses} border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus:ring-gray-500`;
    default:
      return `${baseClasses} bg-red-600 text-white hover:bg-red-700 focus:ring-red-500`;
  }
}
