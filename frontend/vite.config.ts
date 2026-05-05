import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const frontendPort = Number(process.env.FRONTEND_PORT || '5173')
const backendPort = Number(process.env.BACKEND_PORT || process.env.SERVER_PORT || '8000')
const backendHost = process.env.BACKEND_HOST || '127.0.0.1'

export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
    strictPort: false,
    proxy: {
      '/api': {
        target: `http://${backendHost}:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'markdown-vendor': ['react-markdown', 'remark-gfm'],
          'charts-vendor': ['echarts', 'echarts-for-react'],
        },
      },
    },
  },
})
