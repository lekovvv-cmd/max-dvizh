import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type { Group } from '../../app/api'
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
