import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { api, type Dvizh, type Group, type Taxonomy } from './api'

const group: Group = {
  id: 'group-1',
  name: 'Друзья',
  city_slug: 'msk',
  member_count: 3,
  max_chat_bound: false,
}
const taxonomy: Taxonomy = {
  directions: [
    { id: 'games', label: 'Игры' },
    { id: 'culture', label: 'Культура' },
  ],
  activities: [
    { id: 'quest', label: 'Квест', directions: ['games'] },
    { id: 'pc_club', label: 'ПК-клуб', directions: ['games'] },
    { id: 'museum', label: 'Музей', directions: ['culture'] },
  ],
}

function candidate(id: string) {
  const starts = new Date(Date.now() + 3 * 60 * 60 * 1000)
  return {
    id,
    title: `Квест ${id}`,
    venue_name: 'Лабиринт',
    starts_at: starts.toISOString(),
    ends_at: new Date(starts.getTime() + 60 * 60 * 1000).toISOString(),
    price_text: '500 ₽',
    price_min: 500,
    distance_km: 2,
    address_text: 'Ленина, 1',
    source_url: null,
    image_url: null,
    activity_ids: ['quest'],
    compatibility: 'EXACT',
    budget_delta: null,
    expires_at: new Date(starts.getTime() - 10 * 60 * 1000).toISOString(),
    my_reaction: null,
    position: Number(id),
  }
}

function dvizh(status = 'CHOOSING_CANDIDATES'): Dvizh {
  return {
    id: 'session-1',
    signal_batch_id: 'batch-1',
    group_id: group.id,
    group_name: group.name,
    status,
    is_initiator: true,
    activity_ids: ['quest'],
    min_people: 3,
    max_people: 3,
    available_from: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
    available_to: new Date(Date.now() + 5 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
    active_candidate_id: null,
    candidates: [candidate('1'), candidate('2')],
    chosen_count: 0,
    reaction_count: 0,
    confirmed_count: 0,
    my_confirmation: null,
    participants: [],
  }
}

function mockData(items: Dvizh[] = []) {
  vi.spyOn(api, 'session').mockResolvedValue({
    id: 'me',
    display_name: 'Антон',
    max_mode: 'DEMO',
    max_chat_id: null,
  })
  vi.spyOn(api, 'groups').mockResolvedValue([group])
  vi.spyOn(api, 'locations').mockResolvedValue([])
  vi.spyOn(api, 'intents').mockResolvedValue([])
  vi.spyOn(api, 'dvizhi').mockResolvedValue(items)
  vi.spyOn(api, 'taxonomy').mockResolvedValue(taxonomy)
}

beforeEach(() => {
  localStorage.clear()
  window.location.hash = ''
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('new Dvizh product route', () => {
  it('shows one primary signal action and three product tabs', async () => {
    mockData()
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Есть идея на вечер?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Движи' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Планы' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Подай сигнал' })).toBeInTheDocument()
  })

  it('loads direction and concrete activities from backend taxonomy', async () => {
    mockData()
    const submit = vi
      .spyOn(api, 'signalBatch')
      .mockResolvedValue({ signal_batch_id: 'batch-1', dvizhi: [] })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Пропустить' }))
    fireEvent.click(screen.getByRole('button', { name: 'Подать сигнал' }))
    expect(screen.getByRole('button', { name: 'Игры' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Квест' }))
    fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1))
    expect(submit.mock.calls[0][0]).toMatchObject({
      activity_categories: ['quest'],
      group_ids: ['group-1'],
    })
  })

  it('opens the exact Dvizh from a MAX startapp deep link', async () => {
    mockData([dvizh()])
    window.location.hash = '#startapp=dvizh_session-1'
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Куда пошёл бы?' })).toBeInTheDocument()
    expect(screen.getByText('Квест 1')).toBeInTheDocument()
    expect(screen.getByText('1 из 2')).toBeInTheDocument()
  })

  it('reads the documented MAX WebAppStartParam deep link', async () => {
    mockData([dvizh()])
    window.location.hash = '#WebAppStartParam=dvizh_session-1'
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Куда пошёл бы?' })).toBeInTheDocument()
    expect(screen.getByText('Квест 1')).toBeInTheDocument()
  })

  it('separates collecting and gathered sessions in Движи', async () => {
    const active = dvizh('COLLECTING_REACTIONS')
    const gathered = {
      ...dvizh('GATHERED'),
      id: 'session-2',
      participants: [{ id: 'a', display_name: 'Антон' }],
    }
    mockData([active, gathered])
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Движи' }))
    expect(screen.getByRole('heading', { name: 'Собираются' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Собрались' })).toBeInTheDocument()
  })

  it('shows candidate onboarding only when a candidate exists', async () => {
    localStorage.setItem('dvizh-onboarding-v1-signal', 'done')
    mockData([dvizh()])
    render(<App />)
    expect(await screen.findByRole('dialog', { name: 'Выбери, куда пошёл бы' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Далее' }))
    expect(localStorage.getItem('dvizh-onboarding-v1-choice')).toBe('done')
  })
})
