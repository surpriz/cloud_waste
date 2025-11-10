"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Global error boundary - catches errors in root layout
 * Uses inline styles to work even if CSS fails to load
 */
export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    // Log critical error
    console.error("Critical error caught by global boundary:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          padding: 0,
          fontFamily:
            'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          background: "linear-gradient(135deg, #DC2626 0%, #EA580C 100%)",
          color: "white",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            textAlign: "center",
            padding: "2rem",
            maxWidth: "600px",
          }}
        >
          {/* Error Icon (SVG) */}
          <svg
            width="120"
            height="120"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ margin: "0 auto 2rem", opacity: 0.9 }}
          >
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>

          <h1
            style={{
              fontSize: "6rem",
              fontWeight: "900",
              margin: "0 0 1rem",
              lineHeight: 1,
            }}
          >
            500
          </h1>

          <h2
            style={{
              fontSize: "2rem",
              fontWeight: "700",
              margin: "0 0 1rem",
            }}
          >
            Erreur Critique
          </h2>

          <p
            style={{
              fontSize: "1.125rem",
              opacity: 0.9,
              margin: "0 0 2rem",
            }}
          >
            Une erreur critique s'est produite. L'application ne peut pas
            continuer.
          </p>

          {/* Error details (dev only) */}
          {process.env.NODE_ENV === "development" && (
            <div
              style={{
                backgroundColor: "rgba(255, 255, 255, 0.1)",
                padding: "1rem",
                borderRadius: "0.5rem",
                marginBottom: "2rem",
                textAlign: "left",
                fontSize: "0.875rem",
                fontFamily: "monospace",
                overflowX: "auto",
              }}
            >
              <p style={{ margin: "0 0 0.5rem", wordBreak: "break-all" }}>
                <strong>Error:</strong> {error.message}
              </p>
              {error.digest && (
                <p style={{ margin: 0, fontSize: "0.75rem", opacity: 0.8 }}>
                  <strong>ID:</strong> {error.digest}
                </p>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div
            style={{
              display: "flex",
              gap: "1rem",
              justifyContent: "center",
              flexWrap: "wrap",
            }}
          >
            <button
              onClick={reset}
              style={{
                backgroundColor: "white",
                color: "#DC2626",
                border: "none",
                padding: "1rem 2rem",
                fontSize: "1rem",
                fontWeight: "700",
                borderRadius: "0.75rem",
                cursor: "pointer",
                boxShadow: "0 10px 25px rgba(0, 0, 0, 0.2)",
                transition: "transform 0.2s",
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.transform = "scale(1.05)";
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = "scale(1)";
              }}
            >
              ↻ Réessayer
            </button>
            <a
              href="/"
              style={{
                display: "inline-block",
                backgroundColor: "rgba(255, 255, 255, 0.1)",
                color: "white",
                textDecoration: "none",
                padding: "1rem 2rem",
                fontSize: "1rem",
                fontWeight: "600",
                borderRadius: "0.75rem",
                border: "2px solid rgba(255, 255, 255, 0.3)",
                transition: "all 0.2s",
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.backgroundColor =
                  "rgba(255, 255, 255, 0.2)";
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor =
                  "rgba(255, 255, 255, 0.1)";
              }}
            >
              ← Retour à l'accueil
            </a>
          </div>

          {/* Support contact */}
          <p
            style={{
              marginTop: "3rem",
              fontSize: "0.875rem",
              opacity: 0.8,
            }}
          >
            Si le problème persiste, contactez{" "}
            <a
              href="mailto:support@cloudwaste.com"
              style={{ color: "white", textDecoration: "underline" }}
            >
              support@cloudwaste.com
            </a>
          </p>
        </div>
      </body>
    </html>
  );
}
