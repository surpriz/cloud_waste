/**
 * Sentry Edge Configuration
 *
 * This file configures Sentry for Next.js Edge Runtime.
 * Runs in Edge Runtime (Middleware, Edge API Routes).
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  // Sentry DSN from environment variable
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Environment (production, staging, development)
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development",

  // Performance Monitoring
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0, // 10% in prod, 100% in dev

  // Session Replay (disabled for edge runtime)
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,

  // GDPR: Do not send Personally Identifiable Information (PII)
  sendDefaultPii: false,

  // Release tracking (helps identify which version introduced bugs)
  release: process.env.NEXT_PUBLIC_GIT_COMMIT || "dev",

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

    return event;
  },
});
