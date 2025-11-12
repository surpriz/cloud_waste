// This file is used to initialize Sentry for both server and edge runtime
// Next.js 14+ recommends this approach instead of separate config files
// https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation

export async function register() {
  // Initialize Sentry for Node.js (server-side)
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const Sentry = await import("@sentry/nextjs");

    Sentry.init({
      dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
      environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development",
      tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
      replaysSessionSampleRate: 0,
      replaysOnErrorSampleRate: 0,
      attachStacktrace: true,
      maxBreadcrumbs: 50,
      debug: process.env.NODE_ENV === "development",

      beforeSend(event, hint) {
        if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
          return null;
        }

        // Filter out sensitive data
        if (event.breadcrumbs) {
          event.breadcrumbs = event.breadcrumbs.filter((breadcrumb) => {
            const message = breadcrumb.message?.toLowerCase() || "";
            return !message.includes("password") && !message.includes("token") && !message.includes("secret");
          });
        }

        if (process.env.NODE_ENV === "development") {
          console.log("🔍 Sentry event (server):", event.message || event.exception);
        }

        return event;
      },

      ignoreErrors: [
        "NEXT_NOT_FOUND",
        "NEXT_REDIRECT",
        "ECONNREFUSED",
        "ENOTFOUND",
        "ETIMEDOUT",
      ],
    });
  }

  // Initialize Sentry for Edge Runtime
  if (process.env.NEXT_RUNTIME === "edge") {
    const Sentry = await import("@sentry/nextjs");

    Sentry.init({
      dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
      environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development",
      tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
      replaysSessionSampleRate: 0,
      replaysOnErrorSampleRate: 0,
      attachStacktrace: true,
      debug: process.env.NODE_ENV === "development",

      beforeSend(event, hint) {
        if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
          return null;
        }
        return event;
      },
    });
  }
}
