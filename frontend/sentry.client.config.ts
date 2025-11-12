/**
 * Sentry Client Configuration
 *
 * This file configures Sentry for the browser/client-side.
 * Runs in the user's browser.
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  // Sentry DSN from environment variable
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Environment (production, staging, development)
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "production",

  // Performance Monitoring
  tracesSampleRate: 0.1, // 10% of transactions (adjust based on traffic)

  // Session Replay (optional - captures user sessions for debugging)
  // replaysSessionSampleRate: 0.1, // 10% of sessions
  // replaysOnErrorSampleRate: 1.0, // 100% of sessions with errors

  // Integrations
  integrations: [
    // Automatically track React component errors
    Sentry.replayIntegration({
      maskAllText: true, // Mask all text for GDPR compliance
      blockAllMedia: true, // Block all media (images, videos)
    }),
  ],

  // GDPR: Do not send Personally Identifiable Information (PII)
  sendDefaultPii: false,

  // Release tracking (helps identify which version introduced bugs)
  release: process.env.NEXT_PUBLIC_GIT_COMMIT || "dev",

  // Ignore common non-critical errors
  ignoreErrors: [
    // Browser extensions
    "top.GLOBALS",
    "originalPrompt",
    "canvas.contentDocument",
    "MyApp_RemoveAllHighlights",
    "atomicFindClose",
    // Network errors (user's connection issues, not our bugs)
    "Network request failed",
    "NetworkError",
    "Failed to fetch",
    // React errors (these are expected in development)
    "ResizeObserver loop limit exceeded",
  ],

  // Breadcrumbs configuration
  maxBreadcrumbs: 50,

  // Attach stack traces to all messages
  attachStacktrace: true,

  // Enable debug mode (only in development)
  debug: process.env.NODE_ENV === "development",

  // Before send callback (filter/modify events before sending)
  beforeSend(event, hint) {
    // Don't send events if Sentry is not configured
    if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
      return null;
    }

    // Log to console in development
    if (process.env.NODE_ENV === "development") {
      console.log("[Sentry] Event captured:", event);
    }

    return event;
  },
});
