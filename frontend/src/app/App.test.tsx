import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const group = { id: 'group', name: 'Друзья', city_slug: 'ekb', member_count: 4 }
const offer = (id: string, overrides = {}) => ({ id, status: 'PENDING', is_near: false, group_id: 'group', group_name: 'Друзья', title: `ДВИЖ ${id}`, venue_name: 'CyberX', starts_at: '2026-09-17T18:00:00Z', ends_at: '2026-09-17T20:00:00Z', price_text: '400 ₽', price_min: 400, is_demo: false, source_url: null, source_fetched_at: '2026-09-16T18:00:00Z', distance_km: 2.4, potential_count: 4, required_min_people: 3, required_max_people: 5, expires_at: '2026-09-17T17:00:00Z', budget_delta: null, ...overrides })

function mockApi(overrides: Record<string, unknown> = {}) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const body = url.includes('/session') ? { id: '1', display_name: 'Антон' }
      : url.includes('/groups') ? [group]
        : url.includes('/offers') ? []
          : url.includes('/plans') || url.includes('/locations') || url.includes('/intents') ? []
            : []
    const selected = url.includes('/offers') ? overrides.offers ?? body : body
    return Promise.resolve({ ok: true, json: async () => selected })
  }))
}

describe('App', () => {
  afterEach(() => cleanup())
  beforeEach(() => { localStorage.clear(); mockApi() })

  it('guides a first MAX visitor to create a private group', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({ ok: true, json: async () => url.includes('/session') ? { id: '1', display_name: 'Антон' } : [] })))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'С кем собираем ДВИЖ?' })).toBeInTheDocument()
  })

  it('renders the full cross-group offer pool and clear Near action', async () => {
    mockApi({ offers: [offer('1'), offer('2', { group_name: 'Универ', is_near: true, title: 'Боулинг', budget_delta: 100 })] })
    render(<App />)
    expect(await screen.findByText('ДВИЖ 1')).toBeInTheDocument()
    expect(screen.getByText('Боулинг')).toBeInTheDocument()
    expect(screen.getByText('Универ')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Всё равно впишусь' })).toBeInTheDocument()
  })

  it('omits absent price and distance rows from an offer', async () => {
    mockApi({ offers: [offer('без данных', { venue_name: null, price_text: null, price_min: null, distance_km: null })] })
    render(<App />)
    expect(await screen.findByText('ДВИЖ без данных')).toBeInTheDocument()
    expect(screen.queryByText(/Цена неизвестна|Цена не указана|км от твоей точки/)).not.toBeInTheDocument()
  })

  it('opens the progressive Signal wizard from the empty home state', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал ⚡' }))
    expect(screen.getByRole('heading', { name: 'Когда и что?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Дальше' }))
    expect(screen.getByRole('heading', { name: 'Условия' })).toBeInTheDocument()
    expect(screen.getAllByText('Неважно')).toHaveLength(2)
  })

  it('submits null budget and radius when their “Неважно” presets remain selected', async () => {
    const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
      void _init
      const body = url.includes('/session') ? { id: '1', display_name: 'Антон' }
        : url.includes('/groups') ? [group]
          : []
      return Promise.resolve({ ok: true, json: async () => body })
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал ⚡' }))
    fireEvent.click(screen.getByRole('button', { name: 'Дальше' }))
    fireEvent.click(screen.getByRole('button', { name: 'Дальше' }))
    fireEvent.click(screen.getByRole('button', { name: 'Подать сигнал ⚡' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/intents', expect.objectContaining({ method: 'POST', body: expect.any(String) })))
    const signalCall = fetchMock.mock.calls.find(([url]) => url === '/api/v1/intents')
    expect(signalCall).toBeDefined()
    const request = signalCall?.[1]
    expect(request).toBeDefined()
    if (!request) throw new Error('Signal request was not sent')
    expect(JSON.parse(String(request.body))).toMatchObject({ budget_max: null, radius_km: null, origin_location_id: null })
  })

  it('keeps navigation available for AutoSignals and plans', async () => {
    render(<App />)
    await screen.findByText('Пока тихо')
    fireEvent.click(screen.getByRole('button', { name: 'Авто' }))
    expect(screen.getByRole('heading', { name: 'Позови меня, если…' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Планы' }))
    expect(screen.getByRole('heading', { name: 'Ближайшие ДВИЖи' })).toBeInTheDocument()
  })
})
