import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const body = url.includes('/session') ? { id: '1', display_name: 'Антон' } : []
      return Promise.resolve({ ok: true, json: async () => body })
    }))
  })

  it('guides a first MAX visitor to create a private group', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'С кем собираем ДВИЖ?' })).toBeInTheDocument()
  })
})
