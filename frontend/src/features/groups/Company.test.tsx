import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { api, type Group, type Location } from '../../app/api'
import { Company } from './Company'

const first: Group = {
  id: 'friends',
  name: 'Друзья',
  city_slug: 'msk',
  member_count: 3,
  max_chat_bound: false,
  invite_url: 'https://max.ru/invite',
}
const second: Group = {
  id: 'work',
  name: 'Работа',
  city_slug: 'spb',
  member_count: 1,
  max_chat_bound: false,
}
const place: Location = {
  id: 'place-1',
  label: 'Офис',
  city_slug: 'msk',
  kind: 'SAVED',
  address_text: 'Длинный адрес, Москва',
  is_default: false,
}

beforeEach(() => {
  vi.spyOn(api, 'cities').mockResolvedValue([
    { slug: 'msk', name: 'Москва' },
    { slug: 'spb', name: 'Санкт-Петербург' },
  ])
  vi.spyOn(api, 'groupMembers').mockImplementation(async (id) =>
    id === first.id
      ? [
          { id: 'me', display_name: 'Я', is_me: true },
          { id: 'friend', display_name: 'Друг', is_me: false },
        ]
      : [{ id: 'colleague', display_name: 'Коллега', is_me: false }],
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function renderCompany(overrides: Partial<Parameters<typeof Company>[0]> = {}) {
  const props: Parameters<typeof Company>[0] = {
    groups: [first, second],
    active: first,
    locations: [place],
    mode: 'MAX',
    onSelect: vi.fn(),
    onNew: vi.fn(),
    createOpen: false,
    chatAvailable: false,
    onCreateClose: vi.fn(),
    onCreated: vi.fn(),
    onChangeCity: vi.fn().mockResolvedValue({
      group: first,
      cancelled_signals: 0,
      paused_autosignals: 0,
      cancelled_plans: 0,
      invalidated_offers: 0,
    }),
    onAddPlace: vi.fn().mockResolvedValue(place),
    onRenamePlace: vi.fn().mockResolvedValue(undefined),
    onDefaultPlace: vi.fn().mockResolvedValue(undefined),
    onDeletePlace: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
  return { ...render(<Company {...props} />), props }
}

it('marks the active company, opens members, switches company and exposes invite and create actions', async () => {
  const { props, rerender } = renderCompany()
  expect(screen.getByText('3 участника')).toBeInTheDocument()
  expect(screen.getByText('1 участник')).toBeInTheDocument()
  expect(screen.getByText('Текущая')).toBeInTheDocument()
  expect(screen.getByText('Москва · Друзья')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Новая компания' }))
  expect(props.onNew).toHaveBeenCalledTimes(1)
  rerender(<Company {...props} createOpen />)
  expect(screen.getByRole('dialog', { name: 'Создать компанию' })).toBeInTheDocument()
  fireEvent.click(
    within(screen.getByRole('dialog', { name: 'Создать компанию' })).getByRole('button', {
      name: 'Закрыть',
    }),
  )
  rerender(<Company {...props} />)
  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Создать компанию' })).not.toBeInTheDocument(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Открыть компанию Друзья, текущая' }))
  const dialog = await screen.findByRole('dialog', { name: 'Друзья' })
  await waitFor(() => expect(within(dialog).getByText('Друг')).toBeInTheDocument())
  fireEvent.click(within(dialog).getByRole('button', { name: 'Пригласить друзей' }))
  expect(screen.getByRole('dialog', { name: 'Позвать друзей' })).toBeInTheDocument()
  fireEvent.click(
    within(screen.getByRole('dialog', { name: 'Позвать друзей' })).getByRole('button', {
      name: 'Закрыть',
    }),
  )
  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Позвать друзей' })).not.toBeInTheDocument(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Открыть компанию Работа' }))
  expect(props.onSelect).toHaveBeenCalledWith(second)
  rerender(<Company {...props} active={second} />)
  expect(screen.getByText('Санкт-Петербург · Работа')).toBeInTheDocument()
  await waitFor(() => expect(api.groupMembers).toHaveBeenCalledWith(second.id))
})

it('adds a place from the visible current location action and supports rename, default and delete', async () => {
  const getCurrentPosition = vi.fn((success: PositionCallback) =>
    success({ coords: { latitude: 55.75, longitude: 37.62 } } as GeolocationPosition),
  )
  vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } })
  const { props } = renderCompany()
  fireEvent.click(screen.getByRole('button', { name: 'Добавить место' }))
  const addDialog = screen.getByRole('dialog', { name: 'Добавить место?' })
  fireEvent.click(within(addDialog).getByRole('button', { name: 'Взять мою геопозицию' }))
  await waitFor(() => expect(getCurrentPosition).toHaveBeenCalledTimes(1))
  fireEvent.click(within(addDialog).getByRole('button', { name: 'Сохранить' }))
  await waitFor(() =>
    expect(props.onAddPlace).toHaveBeenCalledWith('Моя геопозиция', 55.75, 37.62, null),
  )
  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Добавить место?' })).not.toBeInTheDocument(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Изменить место Офис' }))
  const editDialog = screen.getByRole('dialog', { name: 'Изменить место' })
  fireEvent.change(within(editDialog).getByRole('textbox', { name: 'Название' }), {
    target: { value: 'Офис рядом' },
  })
  fireEvent.click(within(editDialog).getByRole('button', { name: 'Сохранить' }))
  await waitFor(() => expect(props.onRenamePlace).toHaveBeenCalledWith('place-1', 'Офис рядом'))
  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Изменить место' })).not.toBeInTheDocument(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Изменить место Офис' }))
  fireEvent.click(
    within(screen.getByRole('dialog', { name: 'Изменить место' })).getByRole('button', {
      name: 'Сделать основным',
    }),
  )
  await waitFor(() => expect(props.onDefaultPlace).toHaveBeenCalledWith('place-1'))
  await waitFor(() =>
    expect(screen.queryByRole('dialog', { name: 'Изменить место' })).not.toBeInTheDocument(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Изменить место Офис' }))
  fireEvent.click(
    within(screen.getByRole('dialog', { name: 'Изменить место' })).getByRole('button', {
      name: 'Удалить место',
    }),
  )
  await waitFor(() => expect(props.onDeletePlace).toHaveBeenCalledWith('place-1'))
})

it('changes the active company city through the city picker', async () => {
  const { props } = renderCompany()
  fireEvent.click(screen.getByRole('button', { name: 'Открыть компанию Друзья, текущая' }))
  const dialog = screen.getByRole('dialog', { name: 'Друзья' })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Изменить город компании Друзья' }))
  const cityDialog = screen.getByRole('dialog', { name: 'Сменить город компании?' })
  await waitFor(() =>
    expect(within(cityDialog).getByRole('button', { name: 'Город' })).toBeEnabled(),
  )
  fireEvent.click(within(cityDialog).getByRole('button', { name: 'Город' }))
  fireEvent.click(within(cityDialog).getByRole('button', { name: 'Санкт-Петербург' }))
  fireEvent.click(within(cityDialog).getByRole('button', { name: 'Сменить город' }))
  await waitFor(() => expect(props.onChangeCity).toHaveBeenCalledWith('friends', 'spb'))
})
