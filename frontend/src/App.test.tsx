import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import App from './App'

// Example test demonstrating the test infrastructure setup
// This tests the landing page of the Invoice Builder application

describe('App', () => {
  it('renders the landing page with greeting', () => {
    // Render the App component
    render(<App />)

    // Check that the landing page displays a greeting
    // The greeting shows either "Good Morning" or "Good Afternoon" based on time
    const greetingElement = screen.getByText(/Good (Morning|Afternoon)/i)
    expect(greetingElement).toBeInTheDocument()
  })

  it('renders main navigation options', () => {
    render(<App />)

    // Verify the main action cards are present
    expect(screen.getByText(/Weekly Invoice/i)).toBeInTheDocument()
    expect(screen.getByText(/Monthly Report/i)).toBeInTheDocument()
    expect(screen.getByText(/Edit Profile/i)).toBeInTheDocument()
  })

  it('displays default profile name', () => {
    render(<App />)

    // Check that the default user name "Jane Doe" appears in the greeting
    // Using more specific text pattern since "Jane" appears multiple times
    expect(screen.getByText(/Good (Morning|Afternoon), Jane/i)).toBeInTheDocument()
  })

  it('shows the save folder path', () => {
    render(<App />)

    // The landing page should display the current save folder path
    const folderText = screen.getByText(/Saving to/i)
    expect(folderText).toBeInTheDocument()
  })
})

describe('Accessibility - Error Banner', () => {
  // Mock fetch to trigger config error for error banner display
  beforeEach(() => {
    global.fetch = vi.fn(() =>
      Promise.reject(new Error('Network error'))
    ) as any
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('error banner dismiss button has accessible label', async () => {
    render(<App />)

    // Wait for error banner to appear after failed config fetch
    await waitFor(() => {
      expect(screen.getByText(/Could not load saved profile/i)).toBeInTheDocument()
    })

    // Verify the dismiss button has an accessible label
    const dismissButton = screen.getByRole('button', { name: /dismiss error/i })
    expect(dismissButton).toBeInTheDocument()
    expect(dismissButton).toHaveAttribute('aria-label', 'Dismiss error')
  })
})
