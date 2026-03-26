/**
 * ESLint Configuration for Invoice Builder Frontend
 *
 * This configuration uses ESLint 9.x flat config format and includes:
 * - Core JavaScript best practices
 * - React and JSX specific rules
 * - React Hooks rules to catch common mistakes
 * - React Refresh rules for Vite HMR compatibility
 * - Accessibility (a11y) rules for better UI quality
 *
 * To run linting:
 *   npm run lint        - Check for issues
 *   npm run lint:fix    - Auto-fix issues where possible
 */
import js from '@eslint/js'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import globals from 'globals'

export default [
  // Ignore build output and dependencies
  {
    ignores: ['dist', 'node_modules']
  },

  // Base ESLint recommended rules
  js.configs.recommended,

  // React and JSX configuration
  {
    files: ['**/*.{js,jsx}'],
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y
    },
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      }
    },
    settings: {
      react: {
        version: 'detect'
      }
    },
    rules: {
      // React core rules
      ...react.configs.recommended.rules,
      ...react.configs['jsx-runtime'].rules,

      // React Hooks rules
      ...reactHooks.configs.recommended.rules,

      // React Refresh rules for HMR
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true }
      ],

      // Accessibility rules
      ...jsxA11y.configs.recommended.rules,

      // Additional code quality rules
      'no-unused-vars': ['warn', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_'
      }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'prefer-const': 'warn',
      'no-var': 'error'
    }
  }
]
