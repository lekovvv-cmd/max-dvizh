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

  it('omits absent price and distance rows from an offer', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const body = url.includes('/session')
        ? { id: '1', display_name: 'Антон' }
        : url.includes('/groups')
          ? [{ id: 'group', name: 'Друзья', city_slug: 'ekb', member_count: 2 }]
          : url.includes('/offers')
            ? [{ id: 'offer', status: 'PENDING', is_near: false, group_id: 'group', group_name: 'Друзья', title: 'Квиз', venue_name: null, starts_at: '2026-09-17T18:00:00Z', ends_at: '2026-09-17T20:00:00Z', price_text: null, price_min: null, is_demo: false, source_url: null, source_fetched_at: '2026-09-16T18:00:00Z', distance_km: null, potential_count: 2, required_min_people: 2, required_max_people: 4, expires_at: '2026-09-17T17:00:00Z', budget_delta: null }]
            : []
      return Promise.resolve({ ok: true, json: async () => body })
    }))

    render(<App />)

    expect(await screen.findByText('Квиз')).toBeInTheDocument()
    expect(screen.queryByText(/км от твоей точки/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Цена неизвестна|Цена не указана/)).not.toBeInTheDocument()
  })
})
