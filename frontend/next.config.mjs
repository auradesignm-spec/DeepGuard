/** @type {import('next').NextConfig} */
const nextConfig = {
  // 'standalone' requires symlink support, which Windows without Developer
  // Mode denies (EPERM). Dropped to let the plain build succeed locally.
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
