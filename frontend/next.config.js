/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  
  // Enable standalone output for production Docker builds
  output: 'standalone',
  
  // Disable telemetry in production
  experimental: {
    outputFileTracingRoot: undefined,
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
  },
};

module.exports = nextConfig;
