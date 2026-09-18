import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const group = { id: 'group', name: 'Друзья', city_slug: 'ekb', member_count: 4 }
const city = { slug: 'ekb', name: 'Екатеринбург' }
const offer = { id: 'offer', status: 'PENDING', is_near: false, group_id: 'group', group_name: 'Друзья', title: 'Квиз', venue_name: 'Клуб', starts_at: '2027-09-17T18:00:00Z', ends_at: '2027-09-17T20:00:00Z', price_text: '400 ₽', price_min: 400, is_demo: false, source_url: null, source_fetched_at: '2026-09-16T18:00:00Z', distance_km: null, accepted_count: 2, remaining_capacity: 3, required_min_people: 3, required_max_people: 5, expires_at: '2027-09-17T17:00:00Z', budget_delta: null }

function mockApi(data: { groups?: typeof group[]; offers?: typeof offer[]; intents?: object[]; mode?: string } = {}) {
  const requests = vi.fn((url: string, init?: RequestInit) => {
    const result = url.includes('/session') ? { id: '1', display_name: 'Антон', max_mode: data.mode ?? 'development', max_chat_id: null }
      : url.includes('/cities') ? [city]
        : url.includes('/groups') ? data.groups ?? [group]
          : url.includes('/offers') ? data.offers ?? []
            : url.includes('/intents') ? data.intents ?? []
            : url.includes('/signal-batches') ? { batch_id: 'batch', intents: [] }
              : []
    void init
    return Promise.resolve({ ok: true, json: async () => result })
  })
  vi.stubGlobal('fetch', requests)
  return requests
}

describe('App', () => {
  afterEach(() => cleanup())
  beforeEach(() => { localStorage.clear(); sessionStorage.clear(); mockApi() })

  it('asks a first visitor to name a company and choose its city', async () => {
    mockApi({ groups: [] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Новая компания' })).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: 'Екатеринбург' })).toBeInTheDocument()
  })

  it('shows the full offer pool and accepted count', async () => {
    mockApi({ offers: [offer, { ...offer, id: 'second', title: 'Боулинг', group_name: 'Универ' }] })
    render(<App />)
    expect(await screen.findByText('Квиз')).toBeInTheDocument()
    expect(screen.getByText('Боулинг')).toBeInTheDocument()
    expect(screen.getByText('Универ')).toBeInTheDocument()
  })

  it('creates one Signal batch with optional conditions unset', async () => {
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал ⚡' }))
    expect(screen.getByRole('heading', { name: 'Когда свободен?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Подать сигнал ⚡' }))
    await waitFor(() => expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches')).toBe(true))
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/signal-batches')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ group_ids: ['group'], activity_categories: ['any'], budget_max: null, radius_km: null, origin_location_id: null, min_people: 2, max_people: null })
  })

  it('keeps AutoSignal and plan navigation reachable', async () => {
    render(<App />)
    await screen.findByText('Сигнала пока нет')
    fireEvent.click(screen.getByRole('button', { name: 'Авто' }))
    expect(screen.getByRole('heading', { name: 'Позови меня, если…' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Планы' }))
    expect(screen.getByRole('heading', { name: 'Ближайшие ДВИЖи' })).toBeInTheDocument()
  })

  it('shows a provider outage distinctly and offers a retry', async () => {
    const requests = mockApi({ intents: [{ id: 'intent', type: 'ONE_TIME', status: 'ACTIVE', provider_state: 'PROVIDER_UNAVAILABLE', signal_batch_id: 'batch', group_id: 'group', group_name: 'Друзья', activity_categories: ['any'], available_from: '2027-09-17T18:00:00Z', expires_at: '2027-09-18T00:00:00Z' }] })
    render(<App />)
    expect(await screen.findByText('Источник сейчас недоступен')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить поиск' }))
    await waitFor(() => expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches/batch/refresh')).toBe(true))
  })

  it('keeps demo user switching out of MAX mode', async () => {
    mockApi({ mode: 'MAX' })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(screen.getByRole('heading', { name: 'Компании' })).toBeInTheDocument()
    expect(screen.queryByText('Dev / demo tools')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Сменить пользователя' })).not.toBeInTheDocument()
  })
})
