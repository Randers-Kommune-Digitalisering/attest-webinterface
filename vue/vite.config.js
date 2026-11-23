import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://router.vuejs.org/guide/essentials/navigation.html
// https://vueschool.io/lessons/the-scaffolded-codebase-vite-only

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    proxy: {
      '/api/': {
        target: process.env.API_PROXY_TARGET || 'http://localhost:1880/',
        changeOrigin: false,
      }
    }
  },
  plugins: [
    vue(),
  ],
  define: {
    APP_VERSION: JSON.stringify(process.env.npm_package_version),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})