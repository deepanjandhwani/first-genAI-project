/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === 'production';
const nextConfig = {
  // Static export only for production build (Vercel); dev server needs default mode
  ...(isProd ? { output: 'export' } : {}),
  basePath: isProd ? '/app' : '',
  assetPrefix: isProd ? '/app/' : '',
  trailingSlash: true,
  images: { unoptimized: true },
  async redirects() {
    // In dev, /app has no content (basePath is ''). Send users to root.
    if (!isProd) {
      return [
        { source: '/app', destination: '/', permanent: false },
        { source: '/app/', destination: '/', permanent: false },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;
