// Where this server forwards /api requests. It is an address on the private
// network between the containers, identical in every deployment, so baking it
// into the image at build time does not tie the image to an environment.
const API_PROXY_TARGET = (
  process.env.API_PROXY_TARGET ?? "http://localhost:8000"
).replace(/\/$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  poweredByHeader: false,
  // The browser calls the API on this origin and the server forwards it, so no
  // second public port and no cross-origin request are involved.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          {
            key: "Permissions-Policy",
            value: "geolocation=(), microphone=(), camera=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
