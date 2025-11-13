/**
 * Error handling types for CutCosts
 */

export enum ErrorCategory {
  NETWORK = "network",
  AUTHENTICATION = "authentication",
  AUTHORIZATION = "authorization",
  VALIDATION = "validation",
  NOT_FOUND = "not_found",
  SERVER_ERROR = "server_error",
  UNKNOWN = "unknown",
}

export interface ErrorState {
  category: ErrorCategory;
  message: string;
  code?: string | number;
  details?: Record<string, unknown>;
  timestamp: Date;
  retryable: boolean;
}

export interface ErrorAction {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "outline";
  icon?: React.ComponentType<{ className?: string }>;
}

export interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<ErrorFallbackProps>;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  resetKeys?: unknown[];
}

export interface ErrorFallbackProps {
  error: Error;
  resetError: () => void;
}

export interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ErrorAction;
}

export interface LoadingErrorProps {
  message?: string;
  onRetry?: () => void;
  showDetails?: boolean;
  error?: Error;
}

/**
 * Helper to categorize HTTP errors
 */
export function categorizeHttpError(statusCode: number): ErrorCategory {
  if (statusCode === 401) return ErrorCategory.AUTHENTICATION;
  if (statusCode === 403) return ErrorCategory.AUTHORIZATION;
  if (statusCode === 404) return ErrorCategory.NOT_FOUND;
  if (statusCode === 422) return ErrorCategory.VALIDATION;
  if (statusCode >= 500) return ErrorCategory.SERVER_ERROR;
  if (statusCode >= 400) return ErrorCategory.VALIDATION;
  return ErrorCategory.UNKNOWN;
}

/**
 * Helper to format error messages for users
 */
export function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    return String(error.message);
  }
  return "An unexpected error occurred";
}

/**
 * Helper to check if error is retryable
 */
export function isRetryableError(statusCode?: number): boolean {
  if (!statusCode) return false;
  // Retry on server errors (5xx) and rate limits (429)
  return statusCode >= 500 || statusCode === 429;
}

/**
 * Create ErrorState from API error
 */
export function createErrorState(
  error: unknown,
  statusCode?: number
): ErrorState {
  const category = statusCode
    ? categorizeHttpError(statusCode)
    : ErrorCategory.UNKNOWN;

  return {
    category,
    message: formatErrorMessage(error),
    code: statusCode,
    timestamp: new Date(),
    retryable: isRetryableError(statusCode),
  };
}
