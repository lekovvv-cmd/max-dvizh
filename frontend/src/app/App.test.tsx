import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const group = { id: 'group', name: 'Друзья', city_slug: 'ekb', member_count: 4 }
const city = { slug: 'ekb', name: 'Екатеринбург' }
const moscow = { slug: 'msk', name: 'Москва' }
const offer = {
  id: 'offer',
  status: 'PENDING',
  is_near: false,
  group_id: 'group',
  group_name: 'Друзья',
  title: 'Квиз',
  venue_name: 'Клуб',
  starts_at: '2027-09-17T18:00:00Z',
  ends_at: '2027-09-17T20:00:00Z',
  price_text: '400 ₽',
  price_min: 400,
  is_demo: false,
  source_url: null,
  source_fetched_at: '2026-09-16T18:00:00Z',
  distance_km: null,
  accepted_count: 2,
  conditional_count: 0,
  remaining_capacity: 3,
  required_min_people: 3,
  required_max_people: 5,
  effective_max: 5,
  remaining_to_confirm: 1,
  waitlist_count: 0,
  can_accept: true,
  can_waitlist: false,
  expires_at: '2027-09-17T17:00:00Z',
  budget_delta: null,
}

function mockApi(
  data: {
    groups?: (typeof group)[]
    cities?: (typeof city)[]
    locations?: object[]
    offers?: (typeof offer)[]
    plans?: object[]
    intents?: object[]
    mode?: string
  } = {},
) {
  const requests = vi.fn((url: string, init?: RequestInit) => {
    const result = url.includes('/session')
      ? { id: '1', display_name: 'Антон', max_mode: data.mode ?? 'development', max_chat_id: null }
      : url.includes('/cities')
        ? (data.cities ?? [city])
        : url.includes('/groups/group/city')
          ? {
              group: { ...group, city_slug: 'msk' },
              cancelled_signals: 1,
              paused_autosignals: 1,
              cancelled_plans: 1,
              invalidated_offers: 2,
            }
          : url.includes('/groups')
            ? (data.groups ?? [group])
            : url.includes('/locations')
              ? (data.locations ?? [])
              : url.includes('/offers')
                ? (data.offers ?? [])
                : url.includes('/plans')
                  ? (data.plans ?? [])
                  : url.includes('/intents')
                    ? (data.intents ?? [])
                    : url.includes('/signal-batches')
                      ? { batch_id: 'batch', intents: [] }
                      : []
    void init
    return Promise.resolve({ ok: true, json: async () => result })
  })
  vi.stubGlobal('fetch', requests)
  return requests
}

describe('App', () => {
  afterEach(() => cleanup())
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    mockApi()
  })

  it('asks a first visitor to name a company and choose its city', async () => {
    mockApi({ groups: [] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Создать компанию' })).toBeInTheDocument()
    expect(await screen.findByRole('option', { name: 'Екатеринбург' })).toBeInTheDocument()
  })

  it('shows the full offer pool and accepted count', async () => {
    mockApi({ offers: [offer, { ...offer, id: 'second', title: 'Боулинг', group_name: 'Универ' }] })
    render(<App />)
    expect(await screen.findByText('Квиз')).toBeInTheDocument()
    expect(screen.getByText('Боулинг')).toBeInTheDocument()
    expect(screen.getByText('Универ')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Приглашения' })).toBeInTheDocument()
  })

  it('groups the complete Offer pool by local day', async () => {
    const localDate = (offset: number) => {
      const date = new Date()
      date.setDate(date.getDate() + offset)
      date.setHours(23, 59, 0, 0)
      return date.toISOString()
    }
    mockApi({
      offers: [
        { ...offer, id: 'today', title: 'Сегодняшний квиз', starts_at: localDate(0) },
        { ...offer, id: 'tomorrow', title: 'Завтрашний квиз', starts_at: localDate(1) },
        { ...offer, id: 'later', title: 'Поздний квиз', starts_at: localDate(3) },
      ],
    })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Сегодня' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Завтра' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Позже' })).toBeInTheDocument()
    expect(screen.getByText('Сегодняшний квиз')).toBeInTheDocument()
    expect(screen.getByText('Завтрашний квиз')).toBeInTheDocument()
    expect(screen.getByText('Поздний квиз')).toBeInTheDocument()
  })

  it('shows a newly confirmed plan on Home', async () => {
    mockApi({
      plans: [
        {
          id: 'plan',
          status: 'CONFIRMED',
          title: 'Квиз',
          group_name: 'Друзья',
          starts_at: '2027-09-17T18:00:00Z',
          ends_at: '2027-09-17T20:00:00Z',
          price_text: null,
          price_kind: 'UNKNOWN',
          address_text: null,
          venue_name: 'Клуб',
          opening_hours_unverified: false,
          source_url: null,
          participant_count: 2,
          required_min_people: 2,
          required_max_people: 2,
          remaining_to_confirm: 0,
          remaining_capacity: 0,
          participants: [{ id: '1', display_name: 'Антон' }],
          my_offer_id: 'offer',
          my_status: 'ACCEPTED',
          share_text: 'Квиз',
        },
      ],
    })
    render(<App />)
    expect(await screen.findByText('ДВИЖ СОБРАЛСЯ')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Квиз' })).toBeInTheDocument()
  })

  it('shows the personal condition while keeping confirmed people separate', async () => {
    mockApi({
      plans: [
        {
          id: 'plan',
          status: 'CONFIRMED_OPEN',
          title: 'Квиз',
          group_name: 'Друзья',
          starts_at: '2027-09-17T18:00:00Z',
          ends_at: '2027-09-17T20:00:00Z',
          price_text: null,
          price_kind: 'UNKNOWN',
          address_text: null,
          venue_name: 'Клуб',
          opening_hours_unverified: false,
          source_url: null,
          participant_count: 2,
          conditional_count: 1,
          personal_response_count: 3,
          personal_required_min: 5,
          required_min_people: 2,
          required_max_people: 5,
          remaining_to_confirm: 0,
          remaining_capacity: 2,
          participants: [],
          my_offer_id: 'offer',
          my_status: 'WAITING_CONDITION',
          share_text: 'Квиз',
        },
      ],
    })
    render(<App />)
    expect(await screen.findByText(/Твоё условие: 5 человек · сейчас готовы 3/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Поделиться' })).not.toBeInTheDocument()
  })

  it('does not offer a waitlist for a full range-based plan', async () => {
    mockApi({
      offers: [
        {
          ...offer,
          accepted_count: 3,
          remaining_capacity: 0,
          effective_max: 3,
          can_accept: false,
          can_waitlist: false,
          remaining_to_confirm: 0,
        },
      ],
    })
    render(<App />)
    expect(await screen.findByText(/мест нет/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Встать в лист ожидания' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Я в деле' })).not.toBeInTheDocument()
  })

  it('uses the selected companies city for saved origins and blocks mixed cities', async () => {
    const requests = mockApi({
      groups: [group, { id: 'msk-group', name: 'Московские', city_slug: 'msk', member_count: 3 }],
      locations: [
        {
          id: 'msk-place',
          label: 'Дом в Москве',
          city_slug: 'msk',
          kind: 'SAVED',
          address_text: 'Улица 1',
          is_default: true,
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    fireEvent.click(screen.getByRole('button', { name: /Московские/ }))
    expect(screen.getByText('Выбери компании из одного города')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Друзья/ }))
    fireEvent.click(screen.getByText('Условия'))
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Расстояние до, км' }), {
      target: { value: '5' },
    })
    expect(screen.getByRole('option', { name: 'Дом в Москве · Улица 1' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Подать сигнал' }))
    await waitFor(() =>
      expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches')).toBe(true),
    )
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/signal-batches')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      group_ids: ['msk-group'],
      origin_location_id: 'msk-place',
      radius_km: 5,
    })
  })

  it('creates one Signal batch with optional conditions unset', async () => {
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    expect(screen.getByRole('heading', { name: 'Подать сигнал' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Подать сигнал' }))
    await waitFor(() =>
      expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches')).toBe(true),
    )
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/signal-batches')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      group_ids: ['group'],
      activity_categories: ['any'],
      budget_max: null,
      radius_km: null,
      origin_location_id: null,
      min_people: 2,
      max_people: null,
    })
  })

  it('submits an arbitrary exact group size', async () => {
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    fireEvent.click(screen.getByText('Условия'))
    fireEvent.click(screen.getByRole('button', { name: 'Ровно N' }))
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Сколько человек?' }), {
      target: { value: '7' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Подать сигнал' }))
    await waitFor(() =>
      expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches')).toBe(true),
    )
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/signal-batches')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ min_people: 7, max_people: 7 })
  })

  it('restores an existing exact Signal value while editing', async () => {
    mockApi({
      intents: [
        {
          id: 'intent',
          type: 'ONE_TIME',
          status: 'ACTIVE',
          provider_state: 'NO_SOURCE',
          signal_batch_id: 'batch',
          group_id: 'group',
          group_name: 'Друзья',
          activity_categories: ['games'],
          available_from: '2027-09-17T18:00:00Z',
          available_to: '2027-09-17T22:00:00Z',
          expires_at: '2027-09-17T22:30:00Z',
          budget_max: null,
          radius_km: null,
          origin_location_id: null,
          min_people: 4,
          max_people: 4,
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Изменить' }))
    expect(screen.getByRole('button', { name: 'Ровно N' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('spinbutton', { name: 'Сколько человек?' })).toHaveValue(4)
  })

  it('opens saved conditions when the budget is zero', async () => {
    mockApi({
      intents: [
        {
          id: 'intent',
          type: 'ONE_TIME',
          status: 'ACTIVE',
          provider_state: 'NO_SOURCE',
          signal_batch_id: 'batch',
          group_id: 'group',
          group_name: 'Друзья',
          activity_categories: ['games'],
          available_from: '2027-09-17T18:00:00Z',
          available_to: '2027-09-17T22:00:00Z',
          expires_at: '2027-09-17T22:30:00Z',
          budget_max: 0,
          radius_km: null,
          origin_location_id: null,
          min_people: 2,
          max_people: null,
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Изменить' }))
    expect(screen.getByText('Условия').closest('details')).toHaveAttribute('open')
    expect(screen.getByRole('spinbutton', { name: 'Бюджет до, ₽' })).toHaveValue(0)
  })

  it('uses plural copy when several participants are missing', async () => {
    mockApi({ offers: [{ ...offer, remaining_to_confirm: 3, required_min_people: 5 }] })
    render(<App />)
    expect(await screen.findByText('2 из 5 · нужно ещё 3')).toBeInTheDocument()
  })

  it('restores an existing exact AutoSignal value while editing', async () => {
    mockApi({
      intents: [
        {
          id: 'auto',
          type: 'RECURRING',
          status: 'ACTIVE',
          provider_state: 'NO_SOURCE',
          signal_batch_id: null,
          group_id: 'group',
          group_name: 'Друзья',
          name: 'Семеро',
          activity_category: 'games',
          activity_categories: ['games'],
          weekdays: [4],
          local_start: '18:00',
          local_end: '23:00',
          budget_max: null,
          radius_km: null,
          origin_location_id: null,
          min_people: 7,
          max_people: 7,
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Авто' }))
    fireEvent.click(screen.getByRole('button', { name: 'Изменить Семеро' }))
    expect(screen.getByRole('button', { name: 'Ровно N' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('spinbutton', { name: 'Сколько человек?' })).toHaveValue(7)
  })

  it('confirms before cancelling an active Signal', async () => {
    const requests = mockApi({
      intents: [
        {
          id: 'intent',
          type: 'ONE_TIME',
          status: 'ACTIVE',
          provider_state: 'NO_SOURCE',
          signal_batch_id: 'batch',
          group_id: 'group',
          group_name: 'Друзья',
          activity_categories: ['any'],
          available_from: '2027-09-17T18:00:00Z',
          expires_at: '2027-09-17T22:30:00Z',
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Отменить' }))
    expect(screen.getByRole('dialog', { name: 'Отменить сигнал?' })).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Отменить сигнал?' })).toHaveFocus()
    expect(
      requests.mock.calls.some(
        ([url, init]) => url === '/api/v1/signal-batches/batch' && init?.method === 'DELETE',
      ),
    ).toBe(false)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Отменить сигнал?' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Отменить' }))
    fireEvent.click(screen.getByRole('button', { name: 'Отменить сигнал' }))
    await waitFor(() =>
      expect(
        requests.mock.calls.some(
          ([url, init]) => url === '/api/v1/signal-batches/batch' && init?.method === 'DELETE',
        ),
      ).toBe(true),
    )
  })

  it('keeps saved-place actions compact and keyboard-reachable', async () => {
    mockApi({
      locations: [
        {
          id: 'home',
          label: 'Дом',
          city_slug: 'ekb',
          kind: 'SAVED',
          address_text: 'ул. Ленина, 1',
          is_default: true,
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(await screen.findByText('ул. Ленина, 1')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Переименовать' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Действия с местом Дом' }))
    expect(screen.getByRole('button', { name: 'Переименовать' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Удалить' })).toBeInTheDocument()
  })

  it('changes Company city only after explicit confirmation', async () => {
    const requests = mockApi({ cities: [city, moscow] })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(await screen.findByText('Екатеринбург')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }))
    expect(screen.getByRole('dialog', { name: 'Сменить город компании?' })).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', { name: 'Город' }), { target: { value: 'msk' } })
    fireEvent.click(screen.getByRole('button', { name: 'Сменить город' }))
    await waitFor(() =>
      expect(
        requests.mock.calls.some(
          ([url, init]) => url === '/api/v1/groups/group/city' && init?.method === 'PUT',
        ),
      ).toBe(true),
    )
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/groups/group/city')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ city_slug: 'msk' })
    expect(await screen.findByRole('status')).toHaveTextContent('Отменено сигналов: 1')
  })

  it('keeps AutoSignal and plan navigation reachable', async () => {
    render(<App />)
    await screen.findByText('Сигнала пока нет')
    fireEvent.click(screen.getByRole('button', { name: 'Авто' }))
    expect(screen.getByRole('heading', { name: 'Автосигналы' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Планы' }))
    expect(screen.getByRole('heading', { name: 'Планы' })).toBeInTheDocument()
  })

  it('shows a provider outage distinctly and offers a retry', async () => {
    const requests = mockApi({
      intents: [
        {
          id: 'intent',
          type: 'ONE_TIME',
          status: 'ACTIVE',
          provider_state: 'PROVIDER_UNAVAILABLE',
          signal_batch_id: 'batch',
          group_id: 'group',
          group_name: 'Друзья',
          activity_categories: ['any'],
          available_from: '2027-09-17T18:00:00Z',
          expires_at: '2027-09-18T00:00:00Z',
        },
      ],
    })
    render(<App />)
    expect(await screen.findByText('Источник сейчас недоступен')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Повторить поиск' }))
    await waitFor(() =>
      expect(
        requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches/batch/refresh'),
      ).toBe(true),
    )
  })

  it('keeps demo user switching out of MAX mode', async () => {
    mockApi({ mode: 'MAX' })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(screen.getByRole('heading', { name: 'Компания' })).toBeInTheDocument()
    expect(screen.queryByText('Dev / demo tools')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Сменить пользователя' })).not.toBeInTheDocument()
  })
})
