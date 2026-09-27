import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { api } from '../../app/api'
import { PlacePicker, type SelectedPlace } from './PlacePicker'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

it('offers addresses while typing and requires choosing a suggestion', async () => {
  const suggest = vi.spyOn(api, 'suggestLocations').mockResolvedValue([
    {
      id: 'W:1',
      title: 'проспект Ленина 1',
      subtitle: 'Екатеринбург',
      address_text: 'проспект Ленина 1, Екатеринбург',
      latitude: 56.838,
      longitude: 60.58,
    },
  ])
  const onSelect = vi.fn<(place: SelectedPlace | null) => void>()
  const view = render(<PlacePicker city="ekb" value={null} onSelect={onSelect} />)
  fireEvent.change(screen.getByLabelText('Адрес или название места'), {
    target: { value: 'Ленина 1' },
  })
  await waitFor(() => expect(suggest).toHaveBeenCalledWith('Ленина 1', 'ekb', expect.anything()))
  fireEvent.click(await screen.findByRole('button', { name: /проспект Ленина 1/ }))
  expect(onSelect).toHaveBeenLastCalledWith({
    latitude: 56.838,
    longitude: 60.58,
    addressText: 'проспект Ленина 1, Екатеринбург',
    title: 'проспект Ленина 1',
  })
  view.rerender(
    <PlacePicker city="ekb" value={onSelect.mock.lastCall?.[0] || null} onSelect={onSelect} />,
  )
  expect(screen.getByText('Точка выбрана')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Адрес или название места'), {
    target: { value: 'Мира' },
  })
  expect(onSelect).toHaveBeenLastCalledWith(null)
})
