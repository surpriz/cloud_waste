"use client";

import { useEffect, useRef } from "react";
import * as Sentry from "@sentry/nextjs";

export function SentryProvider({ children }: { children: React.ReactNode }) {
  const isInitialized = useRef(false);

  useEffect(() => {
    // Initialize Sentry only once on client-side
    if (isInitialized.current || typeof window === "undefined") {
      return;
    }

    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    const environment = process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV || "development";

    console.log("🔍 [SentryProvider] Initialisation Sentry...");
    console.log("🔍 [SentryProvider] DSN:", dsn);
    console.log("🔍 [SentryProvider] Environment:", environment);

    if (!dsn) {
      console.warn("⚠️ [SentryProvider] Sentry DSN non défini - Error tracking désactivé");
      return;
    }

    try {
      Sentry.init({
        dsn,
        environment,
        tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 0,
        attachStacktrace: true,
        maxBreadcrumbs: 50,
        debug: process.env.NODE_ENV === "development",

        beforeSend(event, hint) {
          if (process.env.NODE_ENV === "development") {
            console.log("🔍 [Sentry] Envoi événement:", event.message || event.exception);
          }
          return event;
        },

        ignoreErrors: [
          "Non-Error promise rejection captured",
          "ResizeObserver loop limit exceeded",
          "ResizeObserver loop completed with undelivered notifications",
          "NetworkError",
          "Network request failed",
          "Failed to fetch",
          "Load failed",
        ],
      });

      isInitialized.current = true;
      console.log("✅ [SentryProvider] Sentry initialisé avec succès !");

      // Make Sentry available globally for console testing
      if (typeof window !== "undefined") {
        (window as any).Sentry = Sentry;
        console.log("✅ [SentryProvider] window.Sentry disponible pour tests console");
      }
    } catch (error) {
      console.error("❌ [SentryProvider] Erreur lors de l'initialisation Sentry:", error);
    }
  }, []);

  return <>{children}</>;
}
