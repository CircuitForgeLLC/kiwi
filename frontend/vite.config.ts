import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath, URL } from 'node:url'

// Ensure start_url/scope match the deployment base path so the PWA launches
// at the correct URL (e.g. /kiwi/ in cloud, / in local dev) rather than the
// site root (which on menagerie.circuitforge.tech is the account page).
const rawBase = process.env.VITE_BASE_URL ?? '/'
const appBase = rawBase.endsWith('/') ? rawBase : rawBase + '/'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      // generateSW strategy: Workbox builds the service worker at build time.
      // autoUpdate means new versions install in the background and activate
      // on next navigation — no "click to reload" prompt needed.
      strategies: 'generateSW',
      includeAssets: ['icons/icon-192.png', 'icons/icon-512.png', 'icons/maskable-192.png', 'icons/maskable-512.png'],
      manifest: {
        name: 'Kiwi — Pantry Tracker',
        short_name: 'Kiwi',
        description: 'Track your pantry, cut food waste, get recipe ideas from what you have.',
        theme_color: '#e8a820',
        background_color: '#1e1c1a',
        display: 'standalone',
        orientation: 'portrait',
        scope: appBase,
        start_url: appBase,
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/maskable-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: '/icons/maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Precache the built JS/CSS/HTML shell. API calls are always network-first.
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            // API: network-first, fall back to cache for 1 minute
            urlPattern: /^\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'kiwi-api-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 },
            },
          },
          {
            // Google Fonts: cache-first (fonts rarely change)
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
        ],
      },
    }),
  ],
  base: process.env.VITE_BASE_URL ?? '/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name]-[hash:16].js',
        chunkFileNames: 'assets/[name]-[hash:16].js',
        assetFileNames: 'assets/[name]-[hash:16].[ext]',
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8512',
        changeOrigin: true,
      },
    },
  },
})
