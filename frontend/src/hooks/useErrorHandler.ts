import { useCallback, useState } from "react";
import {
  ErrorState,
  createErrorState,
  formatErrorMessage,
} from "@/types/errors";

interface UseErrorHandlerReturn {
  error: ErrorState | null;
  setError: (error: unknown, statusCode?: number) => void;
  clearError: () => void;
  hasError: boolean;
}

/**
 * Error Handler Hook
 *
 * Manages error state with automatic categorization and formatting.
 * Provides consistent error handling across the application.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { error, setError, clearError, hasError } = useErrorHandler();
 *
 *   const fetchData = async () => {
 *     try {
 *       clearError();
 *       const response = await api.getData();
 *       // ...
 *     } catch (err) {
 *       setError(err, response?.status);
 *     }
 *   };
 *
 *   if (hasError) {
 *     return <ErrorState message={error.message} />;
 *   }
 *
 *   return <div>...</div>;
 * }
 * ```
 */
export function useErrorHandler(): UseErrorHandlerReturn {
  const [error, setErrorState] = useState<ErrorState | null>(null);

  const setError = useCallback((error: unknown, statusCode?: number) => {
    const errorState = createErrorState(error, statusCode);

    // Log error in development
    if (process.env.NODE_ENV === "development") {
      console.error("[useErrorHandler]", {
        category: errorState.category,
        message: errorState.message,
        code: errorState.code,
        retryable: errorState.retryable,
        timestamp: errorState.timestamp,
        details: errorState.details,
      });
    }

    // TODO: Send to error monitoring service
    // logErrorToService(errorState);

    setErrorState(errorState);
  }, []);

  const clearError = useCallback(() => {
    setErrorState(null);
  }, []);

  const hasError = error !== null;

  return {
    error,
    setError,
    clearError,
    hasError,
  };
}

/**
 * Simple Error Handler Hook
 *
 * Lightweight version that only stores error messages.
 * Use when you don't need full error categorization.
 *
 * @example
 * ```tsx
 * const { error, setError, clearError } = useSimpleErrorHandler();
 *
 * try {
 *   await api.call();
 * } catch (err) {
 *   setError(err);
 * }
 * ```
 */
export function useSimpleErrorHandler() {
  const [error, setErrorMessage] = useState<string | null>(null);

  const setError = useCallback((error: unknown) => {
    const message = formatErrorMessage(error);
    setErrorMessage(message);

    if (process.env.NODE_ENV === "development") {
      console.error("[useSimpleErrorHandler]", message);
    }
  }, []);

  const clearError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  return {
    error,
    setError,
    clearError,
    hasError: error !== null,
  };
}
