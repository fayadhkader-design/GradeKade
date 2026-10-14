import type { NextConfig } from "next";
const config: NextConfig = {
  async rewrites() { return [{ source: "/api/:path*", destination: `${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/:path*` }]; },
  async headers() { return [{ source: "/:path*", headers: [{ key: "X-Content-Type-Options", value: "nosniff" }, { key: "Referrer-Policy", value: "same-origin" }] }]; },
  devIndicators: false,
};
export default config;
