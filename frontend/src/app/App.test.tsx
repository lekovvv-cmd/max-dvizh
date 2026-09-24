import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
  budget_delta: null as number | null,
}

function mockApi(
  data: {
    groups?: (typeof group)[]
    members?: { id: string; display_name: string; is_me: boolean }[]
    membersByGroup?: Record<string, { id: string; display_name: string; is_me: boolean }[]>
    cities?: (typeof city)[]
    locations?: object[]
    offers?: (typeof offer)[]
    plans?: object[]
    intents?: object[]
    mode?: string
  } = {},
) {
  const requests = vi.fn((url: string, init?: RequestInit) => {
    const requestedMembersGroup = /^\/api\/v1\/groups\/([^/]+)\/members$/.exec(url)?.[1]
    if (url === '/api/v1/groups' && init?.method === 'POST') {
      const created = {
        ...group,
        ...JSON.parse(String(init.body)),
        id: 'new-group',
        member_count: 1,
      }
      data.groups = [...(data.groups ?? []), created]
      return Promise.resolve({ ok: true, json: async () => created })
    }
    if (url === '/api/v1/locations' && init?.method === 'POST') {
      const place = {
        id: 'new-place',
        ...JSON.parse(String(init.body)),
        address_text: null,
        is_default: false,
      }
      data.locations = [...(data.locations ?? []), place]
      return Promise.resolve({ ok: true, json: async () => place })
    }
    if (url === '/api/v1/autosignals' && init?.method === 'POST')
      return Promise.resolve({ ok: true, json: async () => ({ id: 'auto' }) })
    if (/^\/api\/v1\/autosignals\/[^/]+\/resume$/.test(url) && init?.method === 'POST') {
      const id = url.split('/')[4]
      data.intents = (data.intents ?? []).map((intent) =>
        (intent as { id?: string }).id === id
          ? { ...intent, status: 'ACTIVE', provider_state: 'SEARCHING' }
          : intent,
      )
      return Promise.resolve({
        ok: true,
        json: async () => data.intents?.find((intent) => (intent as { id?: string }).id === id),
      })
    }
    const result = url.includes('/session')
      ? { id: '1', display_name: 'Антон', max_mode: data.mode ?? 'development', max_chat_id: null }
      : url.includes('/cities')
        ? (data.cities ?? [city])
        : requestedMembersGroup
          ? (data.membersByGroup?.[requestedMembersGroup] ??
            data.members ??
            (url.includes('/new-group/')
              ? [{ id: '1', display_name: 'Антон', is_me: true }]
              : [
                  { id: '1', display_name: 'Антон', is_me: true },
                  { id: '2', display_name: 'Маша', is_me: false },
                  { id: '3', display_name: 'Илья', is_me: false },
                  { id: '4', display_name: 'Даша', is_me: false },
                ]))
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
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    window.location.hash = ''
  })
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    mockApi()
  })

  it('asks a first visitor to name a company and choose its city', async () => {
    mockApi({ groups: [] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Создать компанию' })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Город' })).toHaveTextContent('Екатеринбург'),
    )
    expect(screen.getByRole('textbox', { name: 'Название' })).toHaveValue('')
  })

  it('creates the first company and opens the main app', async () => {
    const requests = mockApi({ groups: [] })
    render(<App />)
    fireEvent.change(await screen.findByRole('textbox', { name: 'Название' }), {
      target: { value: 'Наши' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Создать компанию' }))
    expect(
      await screen.findByRole('navigation', { name: 'Основная навигация' }),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Компания' }))
    expect(await screen.findByText('Наши')).toBeInTheDocument()
    const call = requests.mock.calls.find(
      ([url, init]) => url === '/api/v1/groups' && init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      name: 'Наши',
      city_slug: 'ekb',
      bind_current_chat: false,
    })
  })

  it('shows real company member names instead of repeating the count', async () => {
    mockApi({
      groups: [{ ...group, member_count: 2 }],
      members: [
        { id: '1', display_name: 'Антон', is_me: true },
        { id: '2', display_name: 'Маша', is_me: false },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(await screen.findByRole('heading', { name: 'Кто в компании' })).toBeInTheDocument()
    expect(await screen.findByText('Маша')).toBeInTheDocument()
    expect(screen.getByText('Антон')).toBeInTheDocument()
  })

  it('switches companies in place and shows their members below the company list', async () => {
    mockApi({
      groups: [group, { ...group, id: 'work', name: 'Работа', member_count: 2 }],
      membersByGroup: {
        group: [
          { id: '1', display_name: 'Антон', is_me: true },
          { id: '2', display_name: 'Маша', is_me: false },
        ],
        work: [
          { id: '1', display_name: 'Антон', is_me: true },
          { id: '3', display_name: 'Нина', is_me: false },
        ],
      },
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(await screen.findByText('Маша')).toBeInTheDocument()
    const companies = screen.getByRole('heading', { name: 'Мои компании' })
    const members = screen.getByRole('heading', { name: 'Кто в компании' })
    expect(
      companies.compareDocumentPosition(members) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Работа/ }))
    expect(screen.getByRole('navigation', { name: 'Основная навигация' })).toContainElement(
      screen.getByRole('button', { name: 'Компания' }),
    )
    expect(screen.getByRole('button', { name: 'Компания' })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByText('Нина')).toBeInTheDocument()
    expect(screen.queryByText('Маша')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Работа/ })).toHaveTextContent('Текущая')
  })

  it('explains preset hours and describes a six-person company', async () => {
    mockApi({
      groups: [
        {
          ...group,
          name: 'Работа — команда любителей вечерних прогулок и настольных игр',
          member_count: 6,
        },
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    expect(screen.getByRole('button', { name: /Завтра вечером.*18:00–23:00/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /На выходных.*18:00–23:00/ })).toBeInTheDocument()
    expect(screen.getByText(/найди занятие в каталоге/)).toBeInTheDocument()
    expect(screen.getByText('Ты и ещё 5 человек')).toBeInTheDocument()
  })

  it('shows the full offer pool and accepted count', async () => {
    mockApi({ offers: [offer, { ...offer, id: 'second', title: 'Боулинг', group_name: 'Универ' }] })
    render(<App />)
    expect(await screen.findByText('Квиз')).toBeInTheDocument()
    expect(screen.getByText('Боулинг')).toBeInTheDocument()
    expect(screen.getByText('Универ')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Приглашения' })).toBeInTheDocument()
  })

  it('keeps the primary signal action above active signals and invitations', async () => {
    mockApi({
      offers: [offer],
      intents: [
        {
          id: 'intent',
          type: 'ONE_TIME',
          status: 'ACTIVE',
          provider_state: 'SEARCHING',
          signal_batch_id: 'batch',
          group_id: 'group',
          group_name: 'Друзья',
          activity_categories: ['games'],
          available_from: '2027-09-17T18:00:00Z',
          available_to: '2027-09-17T20:00:00Z',
          expires_at: '2027-09-18T00:00:00Z',
          budget_max: null,
          radius_km: null,
        },
      ],
    })
    render(<App />)
    const action = await screen.findByRole('button', { name: 'Подать сигнал' })
    const hero = screen.getByRole('region', { name: 'Когда двигаемся?' })
    const activeSignals = screen.getByRole('region', { name: 'Активные сигналы' })
    expect(action).toBe(within(hero).getByRole('button', { name: 'Подать сигнал' }))
    expect(within(hero).getByText('Собираетесь регулярно?')).toBeInTheDocument()
    expect(
      action.compareDocumentPosition(activeSignals) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Подать сигнал' })).toHaveLength(1)
    fireEvent.click(action)
    expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeInTheDocument()
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

  it('keeps a newly confirmed plan in Plans and off Home', async () => {
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
    await screen.findByRole('navigation', { name: 'Основная навигация' })
    expect(screen.queryByText(/ДВИЖ собрался/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Планы' }))
    expect(await screen.findByText(/ДВИЖ собрался/)).toBeInTheDocument()
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
    await screen.findByRole('navigation', { name: 'Основная навигация' })
    fireEvent.click(screen.getByRole('button', { name: 'Планы' }))
    expect(await screen.findByText('Твоё условие: 3 из 5 готовы')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Поделиться в MAX' })).not.toBeInTheDocument()
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
    expect(await screen.findByText('Квиз')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'В лист ожидания' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Я пойду' })).not.toBeInTheDocument()
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
    expect(screen.getByText('Выбери компании из одного города.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Друзья/ }))
    fireEvent.click(screen.getByText('Бюджет, расстояние и компания'))
    fireEvent.click(screen.getByRole('button', { name: 'Дом в Москве' }))
    fireEvent.click(screen.getByRole('button', { name: 'До 5 км' }))
    fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
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
    expect(screen.getByRole('heading', { name: 'Когда двигаемся?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
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

  it('searches the full activity catalog and submits the chosen directions', async () => {
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    fireEvent.click(screen.getByRole('button', { name: /Все занятия/ }))
    const search = screen.getByRole('searchbox', { name: 'Поиск занятия' })
    fireEvent.change(search, { target: { value: 'театр' } })
    expect(screen.getByRole('button', { name: /Театр.*Спектакли/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Музеи.*Музейные/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Театр.*Спектакли/ }))
    fireEvent.change(search, { target: { value: 'музей' } })
    fireEvent.click(screen.getByRole('button', { name: /Музеи.*Музейные/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
    await waitFor(() =>
      expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches')).toBe(true),
    )
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/signal-batches')
    expect(JSON.parse(String(call?.[1]?.body)).activity_categories).toEqual(['theater', 'museum'])
  })

  it('submits an arbitrary exact group size', async () => {
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    fireEvent.click(screen.getByText('Бюджет, расстояние и компания'))
    fireEvent.click(screen.getByRole('button', { name: 'Ровно…' }))
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Сколько человек?' }), {
      target: { value: '7' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
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
    expect(screen.getByRole('button', { name: 'Ровно…' })).toHaveAttribute('aria-pressed', 'true')
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
    expect(screen.getByText('Бюджет, расстояние и компания').closest('details')).toHaveAttribute(
      'open',
    )
    expect(screen.getByRole('spinbutton', { name: 'Сумма, ₽' })).toHaveValue(0)
  })

  it('uses plural copy when several participants are missing', async () => {
    mockApi({ offers: [{ ...offer, remaining_to_confirm: 3, required_min_people: 5 }] })
    render(<App />)
    expect(await screen.findByText('2 из 5 подтвердили')).toBeInTheDocument()
    expect(screen.getByText('Для плана нужны ещё 3 человека.')).toBeInTheDocument()
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
    fireEvent.click(await screen.findByRole('button', { name: 'Изменить' }))
    expect(screen.getByRole('checkbox', { name: 'Повторять каждую неделю' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Ровно…' })).toHaveAttribute('aria-pressed', 'true')
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
    fireEvent.click(await screen.findByRole('button', { name: 'Остановить' }))
    expect(screen.getByRole('dialog', { name: 'Остановить поиск?' })).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Остановить поиск?' })).toHaveFocus()
    expect(
      requests.mock.calls.some(
        ([url, init]) => url === '/api/v1/signal-batches/batch' && init?.method === 'DELETE',
      ),
    ).toBe(false)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Остановить поиск?' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Остановить' }))
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Остановить поиск?' })).getByRole('button', {
        name: 'Назад',
      }),
    )
    expect(
      requests.mock.calls.some(
        ([url, init]) => url === '/api/v1/signal-batches/batch' && init?.method === 'DELETE',
      ),
    ).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Остановить' }))
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Остановить поиск?' })).getByRole('button', {
        name: 'Остановить',
      }),
    )
    await waitFor(() =>
      expect(
        requests.mock.calls.some(
          ([url, init]) => url === '/api/v1/signal-batches/batch' && init?.method === 'DELETE',
        ),
      ).toBe(true),
    )
  })

  it('offers resume instead of stop for a paused recurring search', async () => {
    const requests = mockApi({
      intents: [
        {
          id: 'auto',
          type: 'RECURRING',
          status: 'PAUSED',
          provider_state: 'NO_SOURCE',
          signal_batch_id: null,
          group_id: 'group',
          group_name: 'Друзья',
          activity_categories: ['games'],
          weekdays: [5],
        },
      ],
    })
    render(<App />)
    expect(await screen.findByText('Поиск на паузе')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Остановить' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Возобновить' }))
    await waitFor(() =>
      expect(
        requests.mock.calls.some(
          ([url, init]) => url === '/api/v1/autosignals/auto/resume' && init?.method === 'POST',
        ),
      ).toBe(true),
    )
    expect(await screen.findByRole('heading', { name: 'Ищем подходящий план' })).toBeInTheDocument()
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

  it('adds a private place from the Company card using the current position', async () => {
    const getCurrentPosition = vi.fn((success: (position: object) => void) =>
      success({ coords: { latitude: 56.8, longitude: 60.6 } }),
    )
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition },
    })
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    fireEvent.click(screen.getByText('Добавить место'))
    fireEvent.change(screen.getByRole('textbox', { name: 'Название' }), {
      target: { value: 'Работа' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить текущее место' }))
    await waitFor(() => expect(getCurrentPosition).toHaveBeenCalledOnce())
    await waitFor(() => expect(screen.getByText('Работа')).toBeInTheDocument())
    const call = requests.mock.calls.find(
      ([url, init]) => url === '/api/v1/locations' && init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      label: 'Работа',
      city_slug: 'ekb',
      latitude: 56.8,
      longitude: 60.6,
    })
    Reflect.deleteProperty(navigator, 'geolocation')
  })

  it('changes Company city only after explicit confirmation', async () => {
    const requests = mockApi({ cities: [city, moscow] })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Компания' }))
    expect(await screen.findByText('Екатеринбург')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }))
    expect(screen.getByRole('dialog', { name: 'Сменить город компании?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Город' }))
    fireEvent.click(screen.getByRole('button', { name: 'Москва' }))
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
    await screen.findByText('Собираетесь регулярно?')
    expect(screen.queryByRole('button', { name: 'Авто' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Настроить' }))
    expect(screen.getByRole('checkbox', { name: 'Повторять каждую неделю' })).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Закрыть форму' }))
    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }))
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
    expect(await screen.findByText('Источник недоступен')).toBeInTheDocument()
    expect(await screen.findByText('Не удалось загрузить варианты')).toBeInTheDocument()
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

  it('creates a weekly recurring signal from the same form', async () => {
    const requests = mockApi()
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Настроить' }))
    expect(screen.getByRole('checkbox', { name: 'Повторять каждую неделю' })).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
    await waitFor(() =>
      expect(requests.mock.calls.some(([url]) => url === '/api/v1/autosignals')).toBe(true),
    )
    expect(requests.mock.calls.some(([url]) => url === '/api/v1/signal-batches')).toBe(false)
  })

  it('restores an unfinished signal after the mini app is reopened', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    fireEvent.click(screen.getByRole('button', { name: 'Игры' }))
    expect(screen.getByRole('button', { name: /Игры/ })).toHaveAttribute('aria-pressed', 'true')
    cleanup()
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Когда двигаемся?' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Основная навигация' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Игры/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('adds a place over the signal form without losing chosen interests', async () => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: (success: (position: object) => void) =>
          success({ coords: { latitude: 56.8, longitude: 60.6 } }),
      },
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    fireEvent.click(screen.getByRole('button', { name: 'Игры' }))
    fireEvent.click(screen.getByText('Бюджет, расстояние и компания'))
    fireEvent.click(screen.getByRole('button', { name: '+ Добавить место' }))
    fireEvent.click(screen.getByRole('button', { name: 'Использовать мою геопозицию' }))
    expect(await screen.findByText('Точка получена. Можно сохранить место.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить место' }))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Новое место' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: /Игры/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Дом/ })).toHaveAttribute('aria-pressed', 'true')
    Reflect.deleteProperty(navigator, 'geolocation')
  })

  it('asks consent before accepting a near budget match', async () => {
    const requests = mockApi({
      offers: [
        { ...offer, is_near: true, compatibility_kind: 'NEAR', budget_delta: 100 } as typeof offer,
      ],
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Я пойду' }))
    expect(screen.getByRole('dialog', { name: 'Подтвердить этот вариант?' })).toBeInTheDocument()
    expect(requests.mock.calls.some(([url]) => url === '/api/v1/offers/offer/accept')).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Всё равно пойду' }))
    await waitFor(() =>
      expect(requests.mock.calls.some(([url]) => url === '/api/v1/offers/offer/accept')).toBe(true),
    )
    const call = requests.mock.calls.find(([url]) => url === '/api/v1/offers/offer/accept')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ confirm_near_exception: true })
  })

  it('never shows an unverified candidate as an invitation', async () => {
    mockApi({ offers: [{ ...offer, compatibility_kind: 'UNVERIFIED' } as typeof offer] })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Когда двигаемся?' })).toBeInTheDocument()
    expect(screen.queryByText('Квиз')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Я пойду' })).not.toBeInTheDocument()
  })

  it('prevents duplicate submission while a signal request is pending', async () => {
    const base = mockApi()
    let submissions = 0
    vi.stubGlobal('fetch', (url: string, init?: RequestInit) => {
      if (url === '/api/v1/signal-batches' && init?.method === 'POST') {
        submissions += 1
        return new Promise(() => undefined)
      }
      return base(url, init)
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Подать сигнал' }))
    const form = screen.getByRole('button', { name: 'Начать поиск' }).closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    expect(submissions).toBe(1)
    expect(screen.getByRole('heading', { name: 'Ищем подходящий план' })).toBeInTheDocument()
  })

  it('opens an invitation deep link and keeps the three mobile tabs', async () => {
    window.location.hash = '#startapp=offer_offer'
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    mockApi({ offers: [offer] })
    render(<App />)
    expect(await screen.findByText('Квиз')).toBeInTheDocument()
    await waitFor(() => expect(scroll).toHaveBeenCalled())
    const nav = screen.getByRole('navigation', { name: 'Основная навигация' })
    expect(nav.querySelectorAll('button')).toHaveLength(3)
  })

  it('opens the Plans screen from a plan deep link', async () => {
    window.location.hash = '#startapp=plan_plan'
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Планы' })).toBeInTheDocument()
  })

  it('explains an empty catalog and extends the existing time window', async () => {
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
          min_people: 2,
          max_people: null,
        },
      ],
    })
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'На это время ничего не нашли' }),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Добавить завтра' }))
    expect(screen.getByRole('heading', { name: 'Изменить условия' })).toBeInTheDocument()
    const end = screen.getByLabelText('До') as HTMLInputElement
    expect(new Date(end.value).getTime()).toBeGreaterThan(
      new Date('2027-09-17T22:00:00Z').getTime(),
    )
  })

  it('keeps a collecting plan in Plans while waiting for friends', async () => {
    mockApi({
      plans: [
        {
          id: 'plan',
          status: 'COLLECTING',
          title: 'Квиз',
          venue_name: 'Клуб',
          starts_at: '2027-09-17T18:00:00Z',
          ends_at: '2027-09-17T20:00:00Z',
          price_text: null,
          price_kind: 'UNKNOWN',
          address_text: null,
          opening_hours_unverified: false,
          source_url: null,
          participant_count: 2,
          conditional_count: 0,
          personal_response_count: 2,
          personal_required_min: 3,
          required_min_people: 3,
          required_max_people: 5,
          group_id: 'group',
          group_name: 'Друзья',
          remaining_to_confirm: 1,
          remaining_capacity: 3,
          participants: [],
          my_offer_id: 'offer',
          my_status: 'ACCEPTED',
          share_text: 'Квиз',
        },
      ],
    })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Ждём ещё участников' })).toBeInTheDocument()
    expect(screen.queryByText('Ты в деле')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Планы' }))
    expect(await screen.findByText('Ты в деле')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Квиз' })).toBeInTheDocument()
  })
})
