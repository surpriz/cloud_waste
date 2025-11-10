import { AlertCircle, RefreshCw, WifiOff } from "lucide-react";
import { LoadingErrorProps } from "@/types/errors";

/**
 * Loading Error Component
 *
 * Displays an error when data fails to load.
 * Shows retry button and optional error details.
 *
 * @example
 * ```tsx
 * <LoadingError
 *   message="Impossible de charger les ressources orphelines"
 *   onRetry={() => refetch()}
 *   showDetails={true}
 *   error={error}
 * />
 * ```
 */
export function LoadingError({
  message = "Échec du chargement des données",
  onRetry,
  showDetails = false,
  error,
}: LoadingErrorProps) {
  const isNetworkError = error?.message?.toLowerCase().includes("network") ||
    error?.message?.toLowerCase().includes("fetch");

  return (
    <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-orange-200 bg-orange-50/50 p-6 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-orange-100">
        {isNetworkError ? (
          <WifiOff className="h-5 w-5 text-orange-600" />
        ) : (
          <AlertCircle className="h-5 w-5 text-orange-600" />
        )}
      </div>

      <h4 className="mb-1 text-base font-semibold text-gray-900">
        {isNetworkError ? "Problème de connexion" : "Erreur de chargement"}
      </h4>

      <p className="mb-4 max-w-sm text-sm text-gray-600">{message}</p>

      {showDetails && error && process.env.NODE_ENV === "development" && (
        <div className="mb-4 w-full max-w-md rounded-md bg-gray-100 p-3 text-left">
          <p className="mb-1 text-xs font-semibold text-gray-700">
            Détails (dev only):
          </p>
          <pre className="overflow-x-auto text-xs text-gray-600">
            {error.message}
          </pre>
        </div>
      )}

      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2"
        >
          <RefreshCw className="h-4 w-4" />
          Réessayer
        </button>
      )}
    </div>
  );
}

/**
 * Inline Loading Error (Compact version)
 *
 * Smaller version for inline use in cards or small sections.
 */
export function InlineLoadingError({
  message = "Échec du chargement",
  onRetry,
}: Pick<LoadingErrorProps, "message" | "onRetry">) {
  return (
    <div className="flex items-center justify-center gap-3 rounded-md bg-orange-50 p-3">
      <AlertCircle className="h-4 w-4 shrink-0 text-orange-600" />
      <p className="flex-1 text-sm text-gray-700">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs font-medium text-orange-700 transition-colors hover:bg-orange-100"
        >
          <RefreshCw className="h-3 w-3" />
          Réessayer
        </button>
      )}
    </div>
  );
}
