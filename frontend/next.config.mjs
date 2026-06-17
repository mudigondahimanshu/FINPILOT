/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: {
    // Lint is run explicitly in CI; don't fail the build on it.
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
