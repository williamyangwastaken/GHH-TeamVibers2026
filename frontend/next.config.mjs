import { fileURLToPath } from "node:url";

// The offline demo fallback imports BE-B's frozen fixture from ../fixtures/, which
// sits outside frontend/. Widen the bundler root to the repository so it resolves.
const repoRoot = fileURLToPath(new URL("..", import.meta.url));

/** @type {import("next").NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: repoRoot,
  turbopack: {
    root: repoRoot,
  },
};

export default nextConfig;
