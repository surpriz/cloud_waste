"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { ErrorBoundaryProps, ErrorFallbackProps } from "@/types/errors";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Reusable Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI.
 *
 * @example
 * ```tsx
 * <ErrorBoundary
 *   fallback={CustomErrorFallback}
 *   onError={(error, errorInfo) => logToService(error, errorInfo)}
 *   resetKeys={[userId, accountId]}
 * >
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console in development
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught an error:", error, errorInfo);
    }

    // Update state with error info
    this.setState({ errorInfo });

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // TODO: Log to error monitoring service
    // logErrorToService(error, errorInfo);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    const { resetKeys } = this.props;
    const { hasError } = this.state;

    // Reset error boundary if resetKeys change
    if (
      hasError &&
      resetKeys &&
      prevProps.resetKeys &&
      resetKeys.length > 0 &&
      !this.areResetKeysEqual(prevProps.resetKeys, resetKeys)
    ) {
      this.resetErrorBoundary();
    }
  }

  areResetKeysEqual(prevKeys: unknown[], currentKeys: unknown[]): boolean {
    if (prevKeys.length !== currentKeys.length) return false;
    return prevKeys.every((key, index) => key === currentKeys[index]);
  }

  resetErrorBoundary = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback: FallbackComponent } = this.props;

    if (hasError && error) {
      // Use custom fallback if provided
      if (FallbackComponent) {
        return (
          <FallbackComponent
            error={error}
            resetError={this.resetErrorBoundary}
          />
        );
      }

      // Default fallback UI
      return <DefaultErrorFallback error={error} resetError={this.resetErrorBoundary} />;
    }

    return children;
  }
}

/**
 * Default Error Fallback Component
 */
function DefaultErrorFallback({ error, resetError }: ErrorFallbackProps) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-red-200 bg-red-50 p-8 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
        <svg
          className="h-8 w-8 text-red-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>

      <h3 className="mb-2 text-xl font-semibold text-gray-900">
        Oups ! Quelque chose s'est mal passé
      </h3>

      <p className="mb-6 max-w-md text-sm text-gray-600">
        Une erreur inattendue s'est produite. Veuillez réessayer ou contacter
        le support si le problème persiste.
      </p>

      {process.env.NODE_ENV === "development" && (
        <div className="mb-6 w-full max-w-2xl rounded-md bg-gray-100 p-4 text-left">
          <p className="mb-2 text-xs font-semibold text-gray-700">
            Erreur (dev only):
          </p>
          <pre className="overflow-x-auto text-xs text-red-600">
            {error.message}
          </pre>
          {error.stack && (
            <pre className="mt-2 overflow-x-auto text-xs text-gray-600">
              {error.stack}
            </pre>
          )}
        </div>
      )}

      <button
        onClick={resetError}
        className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
        Réessayer
      </button>
    </div>
  );
}
