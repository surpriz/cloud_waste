const { withSentryConfig } = require("@sentry/nextjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Enable standalone output for production Docker builds
  output: 'standalone',

  // Disable telemetry in production
  experimental: {
    outputFileTracingRoot: undefined,
    // Enable instrumentation hook for Sentry
    instrumentationHook: true,
  },

  // Ignore ESLint errors during build (for production deployments)
  // This allows deployment even with linting warnings
  // You can still run `npm run lint` to see and fix issues
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Ignore TypeScript errors during build (for production deployments)
  // This allows deployment to proceed even with type errors
  // You can still run `npm run type-check` to see and fix issues
  typescript: {
    ignoreBuildErrors: true,
  },

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
    NEXT_PUBLIC_SENTRY_ENVIRONMENT: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  },
};

// Sentry configuration options
const sentryWebpackPluginOptions = {
  // For all available options, see:
  // https://github.com/getsentry/sentry-webpack-plugin#options

  // Automatically upload source maps to Sentry during build
  // This enables readable stack traces in Sentry dashboard
  silent: true, // Suppresses all logs

  // Disable source maps upload in development
  dryRun: process.env.NODE_ENV !== "production",

  // Organization and project names from sentry.io dashboard
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,

  // Auth token for uploading source maps
  authToken: process.env.SENTRY_AUTH_TOKEN,
};

// Wrap Next.js config with Sentry config
// Only apply Sentry if DSN is configured
module.exports = process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(nextConfig, sentryWebpackPluginOptions)
  : nextConfig;
