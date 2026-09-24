import type { IconName } from '../ui/Icon'
import { formatEventDate, formatTime } from './format'

export type EventFact = {
  icon: IconName
  value: string
  detail?: string
}

export function eventFacts(event: {
  starts_at: string
  ends_at: string
  venue_name: string | null
  address_text: string | null
  price_text: string | null
  price_kind: string
  distance_km?: number | null
}): EventFact[] {
  const facts: EventFact[] = [
    {
      icon: 'calendar',
      value: formatEventDate(event.starts_at),
      detail: `До ${formatTime(event.ends_at)}`,
    },
  ]
  if (event.venue_name || event.address_text)
    facts.push({
      icon: 'pin',
      value: event.venue_name || event.address_text || '',
      detail: event.venue_name && event.address_text ? event.address_text : undefined,
    })
  if (event.distance_km !== null && event.distance_km !== undefined)
    facts.push({
      icon: 'route',
      value: event.distance_km.toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' км',
      detail: 'От выбранной точки',
    })
  if (event.price_text)
    facts.push({
      icon: 'money',
      value: event.price_text.replace(/\s+с человека$/i, ''),
      detail: /\s+с человека$/i.test(event.price_text)
        ? 'Цена с человека'
        : event.price_kind === 'FROM'
          ? 'Цена может быть выше'
          : undefined,
    })
  return facts
}
