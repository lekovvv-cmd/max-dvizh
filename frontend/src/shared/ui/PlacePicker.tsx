import { useEffect, useState } from 'react'

import { api, type AddressSuggestion } from '../../app/api'
import { currentCoordinates, geolocationError } from '../lib/geolocation'
import { ActionErrorModal } from './ActionErrorModal'
import { useActionError } from './actionErrors'
import { Icon } from './Icon'

export type SelectedPlace = {
  latitude: number
  longitude: number
  addressText: string | null
  title: string
}

export function PlacePicker({
  city,
  value,
  onSelect,
  compact = false,
}: {
  city: string
  value: SelectedPlace | null
  onSelect: (place: SelectedPlace | null) => void
  compact?: boolean
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<AddressSuggestion[]>([])
  const [status, setStatus] = useState<'idle' | 'loading' | 'empty'>('idle')
  const [locating, setLocating] = useState(false)
  const { actionError, showActionError, showActionMessage, dismissActionError } = useActionError()

  useEffect(() => {
    const text = query.trim()
    if (value || text.length < 3) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setStatus('loading')
      void api.suggestLocations(text, city, controller.signal).then(
        (items) => {
          setResults(items)
          setStatus(items.length ? 'idle' : 'empty')
        },
        (reason: unknown) => {
          if (!controller.signal.aborted) {
            setStatus('idle')
            showActionError(reason)
          }
        },
      )
    }, 700)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [city, query, value, showActionError])

  async function chooseCurrent() {
    if (locating) return
    setLocating(true)
    try {
      const point = await currentCoordinates()
      onSelect({ ...point, addressText: null, title: 'Моя геопозиция' })
      setQuery('Моя геопозиция')
      setResults([])
    } catch (reason) {
      showActionMessage({ title: 'Не удалось определить место', message: geolocationError(reason) })
    } finally {
      setLocating(false)
    }
  }

  return (
    <div className={`place-picker${compact ? ' place-picker--compact' : ''}`}>
      <label htmlFor="place-address">Адрес или название места</label>
      <div className="place-picker__input">
        <Icon name="search" size={18} />
        <input
          id="place-address"
          autoComplete="off"
          value={query}
          placeholder={compact ? 'Адрес' : 'Начни вводить адрес'}
          onChange={(event) => {
            setQuery(event.target.value)
            setResults([])
            setStatus('idle')
            onSelect(null)
          }}
        />
      </div>
      {!value && results.length ? (
        <ul className="place-picker__results" aria-label="Подсказки адресов">
          {results.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => {
                  onSelect({
                    latitude: item.latitude,
                    longitude: item.longitude,
                    addressText: item.address_text,
                    title: item.title,
                  })
                  setQuery(item.address_text)
                  setResults([])
                }}
              >
                <Icon name="pin" size={18} />
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.subtitle}</small>
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {status === 'loading' ? (
        <p className="form-hint" role="status">
          Ищем адрес…
        </p>
      ) : null}
      {status === 'empty' ? <p className="form-hint">Ничего не нашли. Уточни запрос.</p> : null}
      {value ? (
        <p className="place-picker__selected" role="status">
          <Icon name="check" size={16} /> Точка выбрана
        </p>
      ) : null}
      <button
        type="button"
        className="place-picker__current"
        disabled={locating}
        onClick={() => void chooseCurrent()}
      >
        <Icon name="pin" size={18} /> {locating ? 'Определяем геопозицию…' : 'Взять мою геопозицию'}
      </button>
      <p className="place-picker__credit">
        Адреса: <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>
        {' · '}
        <a href="https://www.geoapify.com/">Powered by Geoapify</a>
      </p>
      <ActionErrorModal error={actionError} onClose={dismissActionError} />
    </div>
  )
}
