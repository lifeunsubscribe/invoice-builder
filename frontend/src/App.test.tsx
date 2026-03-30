import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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

describe('Profile Save - Race Condition Prevention', () => {
  beforeEach(() => {
    // Mock successful config fetch for initial load
    global.fetch = vi.fn((url) => {
      if (url === '/api/config' && !url.includes('method')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            name: 'Test User',
            address: '123 Test St',
            personalEmail: 'test@example.com',
            rate: 20.0,
            clientName: 'Test Client',
            clientEmail: 'client@example.com',
            accountantEmail: 'accountant@example.com',
            accent: '#c47a86',
            invoiceNote: 'Test note',
            saveFolder: '~/Documents/test-invoices'
          })
        }) as any
      }
      // Mock POST /api/config with delay to simulate real network
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            ok: true,
            json: () => Promise.resolve({})
          } as any)
        }, 100)
      })
    }) as any
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prevents multiple concurrent save requests from rapid clicks', async () => {
    render(<App />)

    // Wait for config to load
    await waitFor(() => {
      expect(screen.getByText(/Good (Morning|Afternoon), Test/i)).toBeInTheDocument()
    })

    // Navigate to profile page
    const editProfileButton = screen.getByText(/Edit Profile/i)
    fireEvent.click(editProfileButton)

    // Wait for profile page to load
    await waitFor(() => {
      expect(screen.getByText(/Save Profile/i)).toBeInTheDocument()
    })

    // Get the save button
    const saveButton = screen.getByText(/Save Profile/i)

    // Rapidly click the save button 5 times
    fireEvent.click(saveButton)
    fireEvent.click(saveButton)
    fireEvent.click(saveButton)
    fireEvent.click(saveButton)
    fireEvent.click(saveButton)

    // Wait for the save operation to complete
    await waitFor(() => {
      const postCalls = (global.fetch as any).mock.calls.filter(
        (call: any[]) => call[1]?.method === 'POST'
      )
      expect(postCalls.length).toBeGreaterThan(0)
    })

    // Verify that fetch was called only ONCE for POST (plus initial GET)
    const postCalls = (global.fetch as any).mock.calls.filter(
      (call: any[]) => call[1]?.method === 'POST'
    )
    expect(postCalls.length).toBe(1)
  })
})

describe('Weekly Submit - Loading State', () => {
  beforeEach(() => {
    // Mock successful config fetch for initial load
    global.fetch = vi.fn((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            name: 'Test User',
            address: '123 Test St',
            personalEmail: 'test@example.com',
            rate: 20.0,
            clientName: 'Test Client',
            clientEmail: 'client@example.com',
            accountantEmail: 'accountant@example.com',
            accent: '#c47a86',
            invoiceNote: 'Test note',
            saveFolder: '~/Documents/test-invoices'
          })
        }) as any
      }
      // Mock scan endpoint (no existing file)
      if (url.includes('/api/scan?')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ found: false })
        }) as any
      }
      // Mock POST /api/submit/weekly with delay to simulate real network
      if (url === '/api/submit/weekly') {
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: () => Promise.resolve({
                sent: ['client@example.com', 'accountant@example.com'],
                saved: '~/Documents/test-invoices/weekly/INV-20260323.pdf'
              })
            } as any)
          }, 100)
        })
      }
      return Promise.reject(new Error('Unexpected fetch'))
    }) as any
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prevents multiple concurrent submit requests from rapid clicks', async () => {
    render(<App />)

    // Wait for config to load
    await waitFor(() => {
      expect(screen.getByText(/Good (Morning|Afternoon), Test/i)).toBeInTheDocument()
    })

    // Navigate to weekly page
    const weeklyButton = screen.getByText(/Weekly Invoice/i)
    fireEvent.click(weeklyButton)

    // Wait for weekly page to load
    await waitFor(() => {
      expect(screen.getByText(/Save & Submit/i)).toBeInTheDocument()
    })

    // Get the submit button
    const submitButton = screen.getByText(/Save & Submit/i)

    // Rapidly click the submit button 5 times
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)

    // Wait for the submit operation to complete
    await waitFor(() => {
      const submitCalls = (global.fetch as any).mock.calls.filter(
        (call: any[]) => call[0] === '/api/submit/weekly'
      )
      expect(submitCalls.length).toBeGreaterThan(0)
    })

    // Verify that fetch was called only ONCE for weekly submit
    const submitCalls = (global.fetch as any).mock.calls.filter(
      (call: any[]) => call[0] === '/api/submit/weekly'
    )
    expect(submitCalls.length).toBe(1)
  })

  it('shows loading state during submission', async () => {
    render(<App />)

    // Wait for config to load
    await waitFor(() => {
      expect(screen.getByText(/Good (Morning|Afternoon), Test/i)).toBeInTheDocument()
    })

    // Navigate to weekly page
    const weeklyButton = screen.getByText(/Weekly Invoice/i)
    fireEvent.click(weeklyButton)

    // Wait for weekly page to load
    await waitFor(() => {
      expect(screen.getByText(/Save & Submit/i)).toBeInTheDocument()
    })

    // Get the submit button
    const submitButton = screen.getByText(/Save & Submit/i)

    // Click submit
    fireEvent.click(submitButton)

    // Verify loading state appears
    await waitFor(() => {
      expect(screen.getByText(/Submitting\.\.\./i)).toBeInTheDocument()
    })

    // Verify button is disabled during submission
    const loadingButton = screen.getByText(/Submitting\.\.\./i)
    expect(loadingButton).toBeDisabled()

    // Wait for submission to complete
    await waitFor(() => {
      expect(screen.queryByText(/Submitting\.\.\./i)).not.toBeInTheDocument()
    })
  })
})

describe('Monthly Submit - Loading State', () => {
  beforeEach(() => {
    // Mock successful config fetch for initial load
    global.fetch = vi.fn((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            name: 'Test User',
            address: '123 Test St',
            personalEmail: 'test@example.com',
            rate: 20.0,
            clientName: 'Test Client',
            clientEmail: 'client@example.com',
            accountantEmail: 'accountant@example.com',
            accent: '#c47a86',
            invoiceNote: 'Test note',
            saveFolder: '~/Documents/test-invoices'
          })
        }) as any
      }
      // Mock scan-month endpoint
      if (url.includes('/api/scan-month?')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            weeks: [
              { label: 'Week 1', invNum: 'INV-20260301', found: false, hours: 0 },
              { label: 'Week 2', invNum: 'INV-20260308', found: false, hours: 0 },
              { label: 'Week 3', invNum: 'INV-20260315', found: false, hours: 0 },
              { label: 'Week 4', invNum: 'INV-20260322', found: false, hours: 0 }
            ],
            monthlyExists: false
          })
        }) as any
      }
      // Mock POST /api/submit/monthly with delay to simulate real network
      if (url === '/api/submit/monthly') {
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: () => Promise.resolve({
                sent: ['accountant@example.com'],
                saved: '~/Documents/test-invoices/monthly/RPT-2026-03.pdf'
              })
            } as any)
          }, 100)
        })
      }
      return Promise.reject(new Error('Unexpected fetch'))
    }) as any
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prevents multiple concurrent submit requests from rapid clicks', async () => {
    render(<App />)

    // Wait for config to load
    await waitFor(() => {
      expect(screen.getByText(/Good (Morning|Afternoon), Test/i)).toBeInTheDocument()
    })

    // Navigate to monthly page
    const monthlyButton = screen.getByText(/Monthly Report/i)
    fireEvent.click(monthlyButton)

    // Wait for monthly page to load and scan to complete
    await waitFor(() => {
      expect(screen.getByText(/Generate & Send Report/i)).toBeInTheDocument()
    })

    // Close scan popup if it appears
    const gotItButton = screen.queryByText(/Got it/i)
    if (gotItButton) {
      fireEvent.click(gotItButton)
    }

    // Get the submit button
    const submitButton = screen.getByText(/Generate & Send Report/i)

    // Rapidly click the submit button 5 times
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)

    // Wait for the submit operation to complete
    await waitFor(() => {
      const submitCalls = (global.fetch as any).mock.calls.filter(
        (call: any[]) => call[0] === '/api/submit/monthly'
      )
      expect(submitCalls.length).toBeGreaterThan(0)
    })

    // Verify that fetch was called only ONCE for monthly submit
    const submitCalls = (global.fetch as any).mock.calls.filter(
      (call: any[]) => call[0] === '/api/submit/monthly'
    )
    expect(submitCalls.length).toBe(1)
  })

  it('shows loading state during submission', async () => {
    render(<App />)

    // Wait for config to load
    await waitFor(() => {
      expect(screen.getByText(/Good (Morning|Afternoon), Test/i)).toBeInTheDocument()
    })

    // Navigate to monthly page
    const monthlyButton = screen.getByText(/Monthly Report/i)
    fireEvent.click(monthlyButton)

    // Wait for monthly page to load
    await waitFor(() => {
      expect(screen.getByText(/Generate & Send Report/i)).toBeInTheDocument()
    })

    // Close scan popup if it appears
    const gotItButton = screen.queryByText(/Got it/i)
    if (gotItButton) {
      fireEvent.click(gotItButton)
    }

    // Get the submit button
    const submitButton = screen.getByText(/Generate & Send Report/i)

    // Click submit
    fireEvent.click(submitButton)

    // Verify loading state appears
    await waitFor(() => {
      expect(screen.getByText(/Sending Report\.\.\./i)).toBeInTheDocument()
    })

    // Verify button is disabled during submission
    const loadingButton = screen.getByText(/Sending Report\.\.\./i)
    expect(loadingButton).toBeDisabled()

    // Wait for submission to complete
    await waitFor(() => {
      expect(screen.queryByText(/Sending Report\.\.\./i)).not.toBeInTheDocument()
    })
  })
})
