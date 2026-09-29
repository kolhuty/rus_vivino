
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'


const basePath = process.env.GITHUB_ACTIONS === 'true' ? '/rus_vivino/' : '/';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: basePath,
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },

  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})