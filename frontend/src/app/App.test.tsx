import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { api, MaxAuthError, type Dvizh, type Group, type Intent, type Taxonomy } from './api'

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

function mockData(items: Dvizh[] = [], onboardingSeen = false) {
  vi.spyOn(api, 'session').mockResolvedValue({
    id: 'me',
    display_name: 'Антон',
    max_mode: 'DEMO',
    max_chat_id: null,
    onboarding_seen: onboardingSeen,
  })
  vi.spyOn(api, 'markOnboardingSeen').mockResolvedValue({ onboarding_seen: true })
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
  it('directs a visitor without MAX authorization to the bot', async () => {
    mockData()
    vi.mocked(api.session).mockRejectedValue(new MaxAuthError(false))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Открой ДВИЖ в MAX' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть через MAX' })).toHaveAttribute(
      'href',
      'https://max.ru/t57_hakaton_max_bot?startapp',
    )
  })

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

  it('opens an existing company invite without a persistent message on the home screen', async () => {
    mockData([], true)
    window.location.hash = '#startapp=invite-token'
    const join = vi.spyOn(api, 'join').mockResolvedValue({ group, already_member: true })
    render(<App />)
    await waitFor(() => expect(join).toHaveBeenCalledWith('invite-token'))
    expect(await screen.findByRole('heading', { name: 'Есть идея на вечер?' })).toBeInTheDocument()
    expect(screen.queryByText('Ты уже участник')).not.toBeInTheDocument()
  })

  it('shows an invalid invitation in a dismissible dialog', async () => {
    mockData([], true)
    window.location.hash = '#startapp=invalid-token'
    vi.spyOn(api, 'join').mockRejectedValue(new Error('Приглашение истекло'))
    render(<App />)
    expect(
      await screen.findByRole('dialog', { name: 'Не удалось открыть приглашение' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Приглашение истекло')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Понятно' }))
    expect(
      screen.queryByRole('dialog', { name: 'Не удалось открыть приглашение' }),
    ).not.toBeInTheDocument()
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

  it('shows all three onboarding steps together on first entry', async () => {
    mockData()
    render(<App />)
    expect(await screen.findByRole('dialog', { name: 'Подай сигнал' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Далее' }))
    expect(screen.getByRole('dialog', { name: 'Выбери варианты' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Далее' }))
    expect(screen.getByRole('dialog', { name: 'Запусти движ' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Понятно' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(api.markOnboardingSeen).toHaveBeenCalled()
  })

  it('skips onboarding for a user who has already opened the app', async () => {
    mockData([], true)
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Есть идея на вечер?' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Подай сигнал' })).not.toBeInTheDocument()
    expect(api.markOnboardingSeen).not.toHaveBeenCalled()
  })

  it('lets the owner pause and soft-delete a recurring signal', async () => {
    mockData()
    const rule: Intent = {
      id: 'rule-1',
      type: 'RECURRING',
      status: 'ACTIVE',
      provider_state: 'SCHEDULED',
      name: 'Пятничный движ',
      city_slug: 'msk',
      group_id: group.id,
      group_name: group.name,
      signal_batch_id: null,
      activity_category: 'quest',
      activity_categories: ['quest'],
      available_from: null,
      available_to: null,
      budget_max: null,
      radius_km: null,
      origin_location_id: null,
      min_people: 2,
      max_people: 12,
      expires_at: null,
      weekdays: [5],
      local_start: '18:00',
      local_end: '23:00',
    }
    vi.mocked(api.intents).mockResolvedValue([rule])
    const pause = vi
      .spyOn(api, 'pauseRecurringSignal')
      .mockResolvedValue({ id: rule.id, status: 'PAUSED' })
    const remove = vi
      .spyOn(api, 'deleteRecurringSignal')
      .mockResolvedValue({ id: rule.id, status: 'DELETED' })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Пропустить' }))
    fireEvent.click(screen.getByRole('button', { name: 'Движи' }))
    fireEvent.click(screen.getByRole('button', { name: 'Приостановить' }))
    await waitFor(() => expect(pause).toHaveBeenCalledWith(rule.id))
    fireEvent.click(screen.getByRole('button', { name: 'Удалить' }))
    expect(screen.getByRole('dialog', { name: 'Удалить автосигнал?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Удалить автосигнал' }))
    await waitFor(() => expect(remove).toHaveBeenCalledWith(rule.id))
  })
})
