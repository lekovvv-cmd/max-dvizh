import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, type Dvizh } from '../../app/api'
import { setActivityTaxonomy } from '../../shared/lib/activityCatalog'
import { DvizhFlow } from './DvizhFlow'

// jsdom represents pointer events as plain Events; use mouse coordinates for gesture tests.
class TestPointerEvent extends MouseEvent {
  pointerId: number
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init)
    this.pointerId = init.pointerId ?? 0
  }
}
globalThis.PointerEvent = TestPointerEvent as typeof PointerEvent

function sample(): Dvizh {
  const start = new Date(Date.now() + 3 * 60 * 60 * 1000)
  return {
    id: 'd1',
    signal_batch_id: 'b1',
    group_id: 'g1',
    group_name: 'Друзья',
    status: 'CHOOSING_CANDIDATES',
    is_initiator: true,
    activity_ids: ['quest'],
    min_people: 3,
    max_people: 3,
    available_from: new Date(start.getTime() - 60 * 60 * 1000).toISOString(),
    available_to: new Date(start.getTime() + 2 * 60 * 60 * 1000).toISOString(),
    expires_at: new Date(start.getTime() + 3 * 60 * 60 * 1000).toISOString(),
    active_candidate_id: null,
    chosen_count: 0,
    reaction_count: 0,
    confirmed_count: 0,
    my_confirmation: null,
    participants: [],
    candidates: [
      {
        id: 'c1',
        title: 'Квест «Лабиринт»',
        venue_name: 'Лабиринт',
        starts_at: start.toISOString(),
        ends_at: new Date(start.getTime() + 60 * 60 * 1000).toISOString(),
        price_text: '500 ₽',
        price_min: 500,
        distance_km: 2,
        address_text: 'Ленина, 1',
        source_url: null,
        image_url: null,
        activity_ids: ['quest'],
        compatibility: 'EXACT',
        budget_delta: null,
        expires_at: new Date(start.getTime() - 10 * 60 * 1000).toISOString(),
        my_reaction: null,
        position: 0,
      },
    ],
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})
setActivityTaxonomy({
  directions: [{ id: 'games', label: 'Игры' }],
  activities: [{ id: 'quest', label: 'Квест', directions: ['games'] }],
})

describe('finite candidate round', () => {
  it('uses the same reaction endpoint for the calm buttons', async () => {
    const item = sample()
    const save = vi.spyOn(api, 'react').mockResolvedValue(item)
    const update = vi.fn()
    render(<DvizhFlow dvizh={item} onUpdate={update} onEdit={vi.fn()} onNew={vi.fn()} />)
    const signal = screen.getByRole('region', { name: 'Сигнал' })
    expect(signal).toHaveTextContent('Твой сигнал')
    expect(signal).toHaveTextContent('Квест')
    expect(signal).toHaveTextContent('Друзья')
    expect(screen.getByText('1 из 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Пошёл бы' }))
    await waitFor(() => expect(save).toHaveBeenCalledWith('d1', 'c1', 'WOULD_GO', false))
    expect(update).toHaveBeenCalled()
  })

  it('keeps the initiator anonymous in the company signal summary', () => {
    const item = sample()
    item.is_initiator = false
    item.status = 'COLLECTING_REACTIONS'
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    const signal = screen.getByRole('region', { name: 'Сигнал' })
    expect(signal).toHaveTextContent('Сигнал компании')
    expect(signal).not.toHaveTextContent('Твой сигнал')
  })

  it('uses right and left pointer gestures with a meaningful threshold', async () => {
    const item = sample()
    const save = vi.spyOn(api, 'react').mockResolvedValue(item)
    const card = render(
      <DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />,
    ).container.querySelector('.swipe-surface') as HTMLElement
    card.setPointerCapture = vi.fn()
    fireEvent.pointerDown(card, { pointerId: 1, clientX: 100 })
    fireEvent.pointerMove(card, { pointerId: 1, clientX: 120 })
    fireEvent.pointerUp(card, { pointerId: 1, clientX: 120 })
    expect(save).not.toHaveBeenCalled()
    fireEvent.pointerDown(card, { pointerId: 2, clientX: 100 })
    fireEvent.pointerMove(card, { pointerId: 2, clientX: 230 })
    fireEvent.pointerUp(card, { pointerId: 2, clientX: 230 })
    await waitFor(() => expect(save).toHaveBeenCalledWith('d1', 'c1', 'WOULD_GO', false))
  })

  it('ends an all-pass round without launching or notifying the group', () => {
    const item = sample()
    item.candidates[0].my_reaction = 'PASS'
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Ничего не выбрал' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Запустить движ' })).not.toBeInTheDocument()
  })

  it('requires separate explicit launch after a positive first round', () => {
    const item = sample()
    item.candidates[0].my_reaction = 'WOULD_GO'
    item.chosen_count = 1
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Выбрано: 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Запустить движ' })).toBeInTheDocument()
  })

  it('shows a summary before launching when the initiator finishes early', () => {
    const item = sample()
    item.chosen_count = 1
    const launch = vi.spyOn(api, 'launch')
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    expect(screen.getByText('1 из 1')).toBeInTheDocument()
    expect(screen.queryByText('Свайп влево или вправо тоже работает')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Закончить выбор' }))
    expect(screen.getByRole('heading', { name: 'Выбрано: 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Запустить движ' })).toBeInTheDocument()
    expect(launch).not.toHaveBeenCalled()
  })

  it('requires in-app consent before accepting a near-budget candidate', async () => {
    const item = sample()
    item.candidates[0].compatibility = 'NEAR'
    item.candidates[0].budget_delta = 200
    const save = vi.spyOn(api, 'react').mockResolvedValue(item)
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Пошёл бы' }))
    expect(screen.getByRole('dialog', { name: 'Чуть дороже' })).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }))
    expect(save).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Пошёл бы' }))
    fireEvent.click(screen.getByRole('button', { name: 'Всё равно пойду' }))
    await waitFor(() => expect(save).toHaveBeenCalledWith('d1', 'c1', 'WOULD_GO', true))
  })

  it('requires separate consent for a near-budget final confirmation', async () => {
    const item = sample()
    item.status = 'AWAITING_CONFIRMATION'
    item.active_candidate_id = 'c1'
    item.candidates[0].my_reaction = 'WOULD_GO'
    item.candidates[0].compatibility = 'NEAR'
    item.candidates[0].budget_delta = 200
    const confirm = vi.spyOn(api, 'confirmDvizh').mockResolvedValue(item)
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Я в деле' }))
    expect(screen.getByRole('dialog', { name: 'Чуть дороже' })).toBeInTheDocument()
    expect(confirm).not.toHaveBeenCalled()
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Чуть дороже' })).getByRole('button', {
        name: 'Я в деле',
      }),
    )
    await waitFor(() => expect(confirm).toHaveBeenCalledWith('d1', 'c1', true))
  })

  it('uses short recovery copy without exposing the provider', () => {
    const item = sample()
    item.status = 'NO_SOURCE'
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Пока ничего не нашли' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Изменить' })).toBeInTheDocument()
    expect(screen.queryByText(/KudaGo/i)).not.toBeInTheDocument()
  })

  it('does not offer reactions for an unverified candidate', () => {
    const item = sample()
    item.candidates[0].compatibility = 'UNVERIFIED'
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Пошёл бы' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Не моё' })).not.toBeInTheDocument()
  })

  it('lets a waitlisted member check for an open place after gathering', async () => {
    const item = sample()
    item.status = 'GATHERED'
    item.active_candidate_id = 'c1'
    item.my_confirmation = 'WAITLISTED'
    item.candidates[0].my_reaction = 'WOULD_GO'
    const save = vi.spyOn(api, 'confirmDvizh').mockResolvedValue(item)
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Проверить место' }))
    await waitFor(() => expect(save).toHaveBeenCalledWith('d1', 'c1', false))
  })

  it('shows a saved confirmation on the detail card', () => {
    const item = sample()
    item.status = 'AWAITING_CONFIRMATION'
    item.active_candidate_id = 'c1'
    item.candidates[0].my_reaction = 'WOULD_GO'
    item.my_confirmation = 'CONFIRMED'
    render(<DvizhFlow dvizh={item} onUpdate={vi.fn()} onEdit={vi.fn()} onNew={vi.fn()} />)
    expect(screen.getByText('Ты в деле')).toBeInTheDocument()
    expect(screen.getByText('Ждём остальных.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Я в деле' })).not.toBeInTheDocument()
    expect(screen.queryByText('Нужно подтвердить')).not.toBeInTheDocument()
  })
})
