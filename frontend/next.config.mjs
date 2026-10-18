import { fileURLToPath } from "node:url";

// The offline demo fallback imports BE-B's frozen fixture from ../fixtures/, which
// sits outside frontend/. Widen the bundler root to the repository so it resolves.
const repoRoot = fileURLToPath(new URL("..", import.meta.url));

/** @type {import("next").NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Next 16 only serves quality 75 unless more are allowed; the hero photo asks for 90.
  images: { qualities: [75, 90] },
  outputFileTracingRoot: repoRoot,
  turbopack: {
    root: repoRoot,
  },
};

export default nextConfig;
