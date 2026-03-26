import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest configuration for Invoice Builder Frontend
// https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // Use jsdom environment to simulate browser APIs
    environment: 'jsdom',

    // Setup file to run before each test file
    setupFiles: ['./src/test/setup.ts'],

    // Global test utilities (optional - makes describe, it, expect available without imports)
    globals: true,

    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.config.{js,ts}',
        '**/dist/',
      ],
      // Coverage thresholds (commented out until baseline is established)
      // Uncomment and adjust these once you have a baseline coverage level
      // lines: 80,
      // functions: 80,
      // branches: 80,
      // statements: 80,
    },

    // Test match patterns
    include: ['src/**/*.{test,spec}.{ts,tsx}'],

    // Exclude patterns
    exclude: [
      'node_modules',
      'dist',
      '.idea',
      '.git',
      '.cache',
    ],
  },
})
