import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Output to project root /dist for Flask static file serving
    outDir: '../dist',
    emptyOutDir: true
  }
})
