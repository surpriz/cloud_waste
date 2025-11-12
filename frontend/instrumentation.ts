/**
 * Next.js Instrumentation Hook
 *
 * This file is automatically called by Next.js when the server starts.
 * Used to initialize Sentry and other observability tools.
 *
 * Documentation: https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register() {
  // Initialize Sentry for server-side (Node.js)
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");

    // Log initialization in development
    if (process.env.NODE_ENV === "development") {
      console.log("✅ Sentry initialized (server-side)");
    }
  }

  // Initialize Sentry for Edge Runtime (Middleware, Edge API Routes)
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");

    // Log initialization in development
    if (process.env.NODE_ENV === "development") {
      console.log("✅ Sentry initialized (edge runtime)");
    }
  }
}
