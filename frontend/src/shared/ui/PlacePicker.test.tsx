import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { api } from '../../app/api'
import { PlacePicker, type SelectedPlace } from './PlacePicker'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
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

it('shows the full address and city for an address outside the current city', async () => {
  vi.spyOn(api, 'suggestLocations').mockResolvedValue([
    {
      id: 'W:moscow',
      title: 'Ленина 1',
      subtitle: 'Ленина 1, Москва',
      address_text: 'Ленина 1, Москва',
      latitude: 55.75,
      longitude: 37.62,
    },
  ])
  const onSelect = vi.fn<(place: SelectedPlace | null) => void>()
  render(<PlacePicker city="ekb" value={null} onSelect={onSelect} />)
  fireEvent.change(screen.getByLabelText('Адрес или название места'), {
    target: { value: 'Ленина 1' },
  })
  expect(await screen.findByText('Ленина 1, Москва')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Ленина 1, Москва/ }))
  expect(onSelect).toHaveBeenLastCalledWith({
    latitude: 55.75,
    longitude: 37.62,
    addressText: 'Ленина 1, Москва',
    title: 'Ленина 1',
  })
})

it('waits for three characters and debounces changes', async () => {
  const suggest = vi.spyOn(api, 'suggestLocations').mockResolvedValue([])
  render(<PlacePicker city="ekb" value={null} onSelect={vi.fn()} />)
  const input = screen.getByLabelText('Адрес или название места')
  fireEvent.change(input, { target: { value: 'Ле' } })
  await new Promise((resolve) => setTimeout(resolve, 750))
  expect(suggest).not.toHaveBeenCalled()
  fireEvent.change(input, { target: { value: 'Лен' } })
  await new Promise((resolve) => setTimeout(resolve, 350))
  fireEvent.change(input, { target: { value: 'Ленина' } })
  await new Promise((resolve) => setTimeout(resolve, 400))
  expect(suggest).not.toHaveBeenCalled()
  await waitFor(() => expect(suggest).toHaveBeenCalledTimes(1))
  expect(suggest).toHaveBeenCalledWith('Ленина', 'ekb', expect.anything())
  expect(await screen.findByText('Ничего не нашли. Уточни запрос.')).toBeInTheDocument()
})

it('aborts an in-flight request when the query changes', async () => {
  const suggest = vi
    .spyOn(api, 'suggestLocations')
    .mockImplementationOnce(() => new Promise(() => {}))
    .mockResolvedValue([])
  render(<PlacePicker city="ekb" value={null} onSelect={vi.fn()} />)
  const input = screen.getByLabelText('Адрес или название места')
  fireEvent.change(input, { target: { value: 'Ленина' } })
  await waitFor(() => expect(suggest).toHaveBeenCalledTimes(1))
  const previousSignal = suggest.mock.calls[0][2]
  fireEvent.change(input, { target: { value: 'Мира' } })
  expect(previousSignal?.aborted).toBe(true)
  await waitFor(() => expect(suggest).toHaveBeenCalledTimes(2))
  expect(suggest.mock.calls[1][0]).toBe('Мира')
})

it('shows provider failure while keeping current geolocation available', async () => {
  vi.spyOn(api, 'suggestLocations').mockRejectedValue(new Error('Unavailable'))
  const getCurrentPosition = vi.fn((success: PositionCallback) =>
    success({ coords: { latitude: 56.838, longitude: 60.58 } } as GeolocationPosition),
  )
  vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } })
  const onSelect = vi.fn<(place: SelectedPlace | null) => void>()
  render(<PlacePicker city="ekb" value={null} onSelect={onSelect} />)
  fireEvent.change(screen.getByLabelText('Адрес или название места'), {
    target: { value: 'Ленина' },
  })
  expect(
    await screen.findByText('Не удалось загрузить адреса. Попробуй ещё раз.'),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Взять мою геопозицию' }))
  await waitFor(() =>
    expect(onSelect).toHaveBeenLastCalledWith({
      latitude: 56.838,
      longitude: 60.58,
      addressText: null,
      title: 'Моя геопозиция',
    }),
  )
  expect(getCurrentPosition).toHaveBeenCalledTimes(1)
})
