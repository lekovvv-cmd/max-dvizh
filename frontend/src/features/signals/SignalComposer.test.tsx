import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { ApiError, api, type Group, type Intent } from '../../app/api'
import { setActivityTaxonomy } from '../../shared/lib/activityCatalog'
import { SignalComposer } from './SignalComposer'

const group: Group = {
  id: 'group-1',
  name: 'Друзья',
  city_slug: 'msk',
  member_count: 1,
  max_chat_bound: false,
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
})

function renderCatalog(existing?: Intent, onDone = vi.fn()) {
  setActivityTaxonomy({
    directions: [
      { id: 'games', label: 'Игры' },
      { id: 'culture', label: 'Культура' },
      { id: 'walk', label: 'Прогулки' },
    ],
    activities: [
      { id: 'quest', label: 'Квест', directions: ['games'] },
      { id: 'board_games', label: 'Настольные игры', directions: ['games'] },
      { id: 'theatre', label: 'Театр', directions: ['culture'] },
      { id: 'museum', label: 'Музей', directions: ['culture'] },
      { id: 'walk', label: 'Погулять', directions: ['walk'] },
    ],
  })
  return render(
    <SignalComposer
      group={group}
      groups={[group]}
      locations={[]}
      activeBatch={existing ? [existing] : undefined}
      adjustment={null}
      onCreateLocation={vi.fn()}
      onDone={onDone}
      onBack={vi.fn()}
    />,
  )
}

it('shows a preflight schedule conflict without opening Tinder or losing signal settings', async () => {
  const onDone = vi.fn()
  const create = vi
    .spyOn(api, 'signalBatch')
    .mockRejectedValue(new ApiError(409, 'У тебя уже есть движ на это время.', 'SCHEDULE_CONFLICT'))
  renderCatalog(undefined, onDone)
  fireEvent.click(screen.getByRole('button', { name: 'Квест' }))
  fireEvent.click(screen.getByText('Бюджет, расстояние и количество друзей'))
  fireEvent.click(screen.getByRole('button', { name: 'Своя сумма' }))
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Сумма, ₽' }), {
    target: { value: '750' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  expect(await screen.findByRole('dialog', { name: 'У тебя уже есть планы' })).toHaveTextContent(
    'Выбери другое время.',
  )
  expect(onDone).not.toHaveBeenCalled()
  expect(screen.queryByText('Куда пошёл бы?')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Понятно' }))
  expect(screen.getByRole('spinbutton', { name: 'Сумма, ₽' })).toHaveValue(750)
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'quest',
  ])
  expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeEnabled()
})

function existingSignal(categories: string[]): Intent {
  return {
    id: 'signal-1',
    type: 'ONE_TIME',
    status: 'ACTIVE',
    provider_state: 'READY',
    name: null,
    city_slug: 'msk',
    group_id: group.id,
    group_name: group.name,
    signal_batch_id: 'batch-1',
    activity_category: categories[0],
    activity_categories: categories,
    available_from: new Date(Date.now() + 86400000).toISOString(),
    available_to: new Date(Date.now() + 90000000).toISOString(),
    budget_max: null,
    radius_km: null,
    origin_location_id: null,
    min_people: 2,
    max_people: null,
    expires_at: null,
    weekdays: null,
    local_start: null,
    local_end: null,
  }
}

it('uses direction tabs only for navigation and keeps selections from several directions', async () => {
  const save = vi.spyOn(api, 'signalBatch').mockResolvedValue({
    signal_batch_id: 'batch-1',
    dvizhi: [],
  })
  renderCatalog()
  const tabs = screen.getByRole('tablist', { name: 'Направление поиска' })
  const activities = () => screen.getByRole('group', { name: 'Занятие' })
  fireEvent.click(within(activities()).getByRole('button', { name: 'Квест' }))
  expect(within(activities()).getByRole('button', { name: 'Квест' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  fireEvent.click(within(tabs).getByRole('tab', { name: 'Культура' }))
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'quest',
  ])
  fireEvent.click(within(activities()).getByRole('button', { name: 'Театр' }))
  fireEvent.click(within(tabs).getByRole('tab', { name: 'Игры' }))
  expect(within(activities()).getByRole('button', { name: 'Квест' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Начать поиск' }))
  await waitFor(() => expect(save).toHaveBeenCalled())
  expect((save.mock.calls[0][0] as { activity_categories: string[] }).activity_categories).toEqual([
    'quest',
    'theatre',
  ])
})

it('keeps several specific activities in one direction', () => {
  renderCatalog()
  fireEvent.click(screen.getByRole('button', { name: 'Квест' }))
  fireEvent.click(screen.getByRole('button', { name: 'Настольные игры' }))
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'quest',
    'board_games',
  ])
})

it('starts without a hidden activity selection when switching directions', () => {
  renderCatalog()
  fireEvent.click(screen.getByRole('tab', { name: 'Культура' }))
  expect(screen.queryByText(/^Выбрано:/)).not.toBeInTheDocument()
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual(
    [],
  )
  expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeDisabled()
})

it('shows only the chosen walk and highlights its activity button', () => {
  renderCatalog()
  fireEvent.click(screen.getByRole('tab', { name: 'Прогулки' }))
  fireEvent.click(screen.getByRole('button', { name: 'Погулять' }))
  expect(screen.getByRole('button', { name: 'Погулять' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('Выбрано: Погулять')).toBeInTheDocument()
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'walk',
  ])
})

it('removes the implicit Games choice from an older new-search draft', () => {
  localStorage.setItem(
    'dvizh-signal-draft-v2:new',
    JSON.stringify({ categories: ['games/*', 'walk'], groupIds: [group.id] }),
  )
  renderCatalog()
  expect(screen.getByText('Выбрано: Погулять')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Погулять' })).toHaveAttribute('aria-pressed', 'true')
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'walk',
  ])
})

it('keeps an explicitly chosen Games wildcard after reopening the draft', () => {
  const view = renderCatalog()
  fireEvent.click(screen.getByRole('button', { name: 'Любое в разделе «Игры»' }))
  view.unmount()
  renderCatalog()
  expect(screen.getByText('Выбрано: Игры')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Любое в разделе «Игры»' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

it('opens the relevant direction while editing and preserves other selected activities', () => {
  renderCatalog(existingSignal(['museum', 'quest']))
  const tabs = screen.getByRole('tablist', { name: 'Направление поиска' })
  expect(within(tabs).getByRole('tab', { name: 'Культура' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  expect(screen.getByRole('button', { name: 'Музей' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(within(tabs).getByRole('tab', { name: 'Игры' }))
  expect(screen.getByRole('button', { name: 'Квест' })).toHaveAttribute('aria-pressed', 'true')
  expect(
    JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:signal-1') || '{}').categories,
  ).toEqual(['museum', 'quest'])
})

it('keeps restored draft selection and does not duplicate a direction wildcard with an activity', () => {
  localStorage.setItem(
    'dvizh-signal-draft-v2:new',
    JSON.stringify({ categories: ['games/*', 'theatre'], groupIds: [group.id], draftVersion: 3 }),
  )
  renderCatalog()
  fireEvent.click(screen.getByRole('tab', { name: 'Культура' }))
  expect(screen.getByRole('button', { name: 'Театр' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('tab', { name: 'Игры' }))
  fireEvent.click(screen.getByRole('button', { name: 'Квест' }))
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'theatre',
    'quest',
  ])
})

it('normalizes redundant wildcard and activity selections in a restored draft', () => {
  localStorage.setItem(
    'dvizh-signal-draft-v2:new',
    JSON.stringify({
      categories: ['games/*', 'quest', 'games/*', 'theatre'],
      groupIds: [group.id],
      draftVersion: 3,
    }),
  )
  renderCatalog()
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'games/*',
    'theatre',
  ])
})

it('adds a search result without changing selections in the current direction', () => {
  renderCatalog()
  fireEvent.click(screen.getByRole('button', { name: 'Любое в разделе «Игры»' }))
  fireEvent.change(screen.getByRole('searchbox', { name: 'Поиск занятия' }), {
    target: { value: 'Театр' },
  })
  fireEvent.click(
    within(screen.getByRole('group', { name: 'Результаты поиска' })).getByRole('button', {
      name: /Театр/,
    }),
  )
  expect(JSON.parse(localStorage.getItem('dvizh-signal-draft-v2:new') || '{}').categories).toEqual([
    'games/*',
    'theatre',
  ])
  expect(screen.getByRole('tab', { name: 'Игры' })).toHaveAttribute('aria-selected', 'true')
})

it('requires a location when a radius is selected', () => {
  renderCatalog()
  fireEvent.click(screen.getByText('Бюджет, расстояние и количество друзей'))
  fireEvent.click(
    within(screen.getByRole('group', { name: 'Радиус' })).getByRole('button', { name: 'До 2 км' }),
  )
  expect(screen.getByText('Теперь выбери точку отсчёта.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeDisabled()
})

it('keeps the custom budget field visible while replacing its value', () => {
  setActivityTaxonomy({
    directions: [{ id: 'games', label: 'Игры' }],
    activities: [{ id: 'quest', label: 'Квест', directions: ['games'] }],
  })
  render(
    <SignalComposer
      group={group}
      groups={[group]}
      locations={[]}
      adjustment={null}
      onCreateLocation={vi.fn()}
      onDone={vi.fn()}
      onBack={vi.fn()}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Квест' }))
  fireEvent.click(screen.getByText('Бюджет, расстояние и количество друзей'))
  fireEvent.click(screen.getByRole('button', { name: 'Своя сумма' }))
  const amount = screen.getByRole('spinbutton', { name: 'Сумма, ₽' })
  expect(amount).toHaveValue(1500)

  fireEvent.change(amount, { target: { value: '' } })
  expect(screen.getByRole('spinbutton', { name: 'Сумма, ₽' })).toHaveValue(null)
  expect(screen.getByRole('button', { name: 'Своя сумма' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeDisabled()

  fireEvent.change(amount, { target: { value: '750' } })
  expect(screen.getByRole('spinbutton', { name: 'Сумма, ₽' })).toHaveValue(750)
  expect(screen.getByRole('button', { name: 'Начать поиск' })).toBeEnabled()
})
