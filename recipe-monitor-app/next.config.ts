import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable React strict mode for better development experience
  reactStrictMode: true,

  // Disable powered by Next.js header
  poweredByHeader: false,

  // Enable compression
  compress: true,

  // Configure image optimization
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.supabase.co',
      },
    ],
  },

  // Experimental features
  experimental: {
    // Enable Server Actions
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },

  // TypeScript configuration
  typescript: {
    // Don't fail production builds on TypeScript errors
    // Remove this once Supabase is configured and types are regenerated
    ignoreBuildErrors: false,
  },

  // ESLint configuration
  eslint: {
    // Run ESLint on production builds
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
