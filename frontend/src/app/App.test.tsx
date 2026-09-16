import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok', service: 'backend', version: '0.1.0' }),
      }),
    )
  })

  it('renders the technical health shell', async () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Технический каркас готов' })).toBeInTheDocument()
    expect(await screen.findByText('Backend: ok · backend v0.1.0')).toBeInTheDocument()
  })
})
