import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: process.cwd(),
  // 本地无 nginx 时（next start 直跑）：/api 转发到后端，便于生产构建直测。
  // 云端 nginx 已把 /api 直接转发后端，请求不会进入 Next，此重写不生效。
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
