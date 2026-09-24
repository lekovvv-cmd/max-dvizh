import { useState } from 'react'
import { Icon } from './Icon'

type City = { slug: string; name: string }

export function CityPicker({
  cities,
  value,
  onChange,
  label = 'Город',
}: {
  cities: City[]
  value: string
  onChange: (slug: string) => void
  label?: string
}) {
  const [open, setOpen] = useState(false)
  const selected = cities.find((city) => city.slug === value)

  return (
    <div className="city-picker">
      <span className="city-picker__label">{label}</span>
      <button
        type="button"
        className="city-picker__trigger"
        aria-label={label}
        aria-expanded={open}
        disabled={!cities.length}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.name ?? 'Выбери город'}</span>
        <Icon name="chevron" size={19} />
      </button>
      {open ? (
        <div className="city-picker__options" role="group" aria-label="Города">
          {cities.map((city) => (
            <button
              key={city.slug}
              type="button"
              className={city.slug === value ? 'is-selected' : ''}
              aria-pressed={city.slug === value}
              onClick={() => {
                onChange(city.slug)
                setOpen(false)
              }}
            >
              {city.name}
              {city.slug === value ? <Icon name="check" size={18} /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
