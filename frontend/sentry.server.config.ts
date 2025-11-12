/**
 * Sentry Server Configuration
 *
 * This file configures Sentry for the Next.js server-side.
 * Runs on the Node.js server.
 */

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  // Sentry DSN from environment variable
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Environment (production, staging, development)
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development",

  // Performance Monitoring
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0, // 10% in prod, 100% in dev

  // Session Replay (disabled for server-side)
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

    // Filter out sensitive data from breadcrumbs
    if (event.breadcrumbs) {
      event.breadcrumbs = event.breadcrumbs.filter((breadcrumb) => {
        const message = breadcrumb.message?.toLowerCase() || "";
        return !message.includes("password") && !message.includes("token") && !message.includes("secret");
      });
    }

    // Log to console in development
    if (process.env.NODE_ENV === "development") {
      console.log("🔍 Sentry event (server):", event.message || event.exception);
    }

    return event;
  },

  // Ignore common non-critical errors
  ignoreErrors: [
    "NEXT_NOT_FOUND",
    "NEXT_REDIRECT",
    "ECONNREFUSED",
    "ENOTFOUND",
    "ETIMEDOUT",
  ],
});
