import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: process.env.VITE_BASE_URL ?? '/',
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
