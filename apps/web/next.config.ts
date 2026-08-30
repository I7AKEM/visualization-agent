import type { NextConfig } from "next";

const buildIdentity = process.env.NEXT_BUILD_ID ?? process.env.GITHUB_SHA;

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  ...(buildIdentity ? { generateBuildId: async () => buildIdentity } : {}),
};

export default nextConfig;
