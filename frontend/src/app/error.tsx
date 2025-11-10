"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home, Bug } from "lucide-react";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log the error to console in development
    if (process.env.NODE_ENV === "development") {
      console.error("Error boundary caught:", error);
    }

    // TODO: Log to error monitoring service (Sentry, LogRocket, etc.)
    // logErrorToService(error);
  }, [error]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-gradient-to-br from-red-600 via-orange-600 to-yellow-600 px-4">
      {/* Animated background */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-1/4 left-1/4 h-96 w-96 rounded-full bg-white blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 h-96 w-96 rounded-full bg-red-300 blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 text-center max-w-2xl">
        {/* Error Icon */}
        <div className="mb-8 flex justify-center">
          <div className="relative">
            <AlertTriangle
              className="h-32 w-32 text-white animate-pulse"
              strokeWidth={1.5}
            />
          </div>
        </div>

        {/* Error Code */}
        <h1 className="text-8xl md:text-9xl font-extrabold text-white/90 leading-none mb-4">
          500
        </h1>

        {/* Title */}
        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
          Oups ! Une erreur est survenue 🔥
        </h2>

        {/* Description */}
        <p className="text-lg md:text-xl text-white/90 mb-4 max-w-md mx-auto">
          Nos serveurs ont rencontré un problème inattendu.
        </p>

        {/* Error message (development only) */}
        {process.env.NODE_ENV === "development" && (
          <div className="mt-6 p-4 bg-white/10 backdrop-blur-sm rounded-lg border border-white/20 text-left max-w-xl mx-auto">
            <p className="text-sm font-mono text-white/80 break-all">
              {error.message}
            </p>
            {error.digest && (
              <p className="text-xs text-white/60 mt-2">
                Error ID: {error.digest}
              </p>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mt-12">
          <button
            onClick={reset}
            className="group inline-flex items-center gap-3 rounded-xl bg-white px-8 py-4 text-lg font-bold text-red-600 transition-all hover:scale-105 hover:shadow-2xl shadow-xl"
          >
            <RefreshCw className="h-5 w-5 group-hover:rotate-180 transition-transform duration-500" />
            Réessayer
          </button>
          <a
            href="/"
            className="inline-flex items-center gap-3 rounded-xl border-2 border-white/30 bg-white/10 backdrop-blur-sm px-8 py-4 text-lg font-semibold text-white transition-all hover:bg-white/20 hover:border-white/50"
          >
            <Home className="h-5 w-5" />
            Retour à l'accueil
          </a>
        </div>

        {/* Report issue link */}
        <div className="mt-12 pt-8 border-t border-white/20">
          <button
            onClick={() => {
              // TODO: Open issue report modal or mailto link
              const subject = encodeURIComponent(
                `[Bug Report] Error: ${error.message}`
              );
              const body = encodeURIComponent(
                `Error occurred:\n\nMessage: ${error.message}\n\nDigest: ${error.digest || "N/A"}\n\nTimestamp: ${new Date().toISOString()}`
              );
              window.location.href = `mailto:support@cloudwaste.com?subject=${subject}&body=${body}`;
            }}
            className="inline-flex items-center gap-2 text-white/80 hover:text-white transition-colors text-sm"
          >
            <Bug className="h-4 w-4" />
            Signaler ce problème
          </button>
        </div>
      </div>
    </div>
  );
}
