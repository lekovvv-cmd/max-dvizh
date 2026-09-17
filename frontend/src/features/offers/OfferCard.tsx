import { Button } from '@maxhub/max-ui'
import { useState } from 'react'

import { api } from '../../app/api'
import type { Offer } from '../../app/api'
import { formatDateTime, formatTime } from '../../shared/lib/format'

export function OfferCard({ offer, onChanged }: { offer: Offer; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function act(accept: boolean) {
    setBusy(true); setError('')
    try {
      if (accept) await api.accept(offer.id, offer.is_near)
      else await api.reject(offer.id)
      onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось обработать выбор')
    } finally { setBusy(false) }
  }

  const hasDetails = offer.price_text !== null || offer.distance_km !== null
  return <article className={`offer-card ${offer.is_near ? 'offer-card--near' : ''}`}>
    <div className="offer-card__head"><span className="group-chip">{offer.group_name}</span>{offer.is_demo ? <span className="demo-mark">Демо</span> : null}</div>
    <h3>{offer.title}</h3>
    <p className="offer-card__when">{formatDateTime(offer.starts_at)} — {formatTime(offer.ends_at)}</p>
    {offer.venue_name ? <p className="offer-card__venue">{offer.venue_name}</p> : null}
    {hasDetails ? <p className="offer-card__details">{offer.price_text}{offer.price_text && offer.distance_km !== null ? ' · ' : null}{offer.distance_km !== null ? `${offer.distance_km.toFixed(1)} км` : null}</p> : null}
    <p className="offer-card__people">{offer.potential_count} потенциально · нужно {offer.required_min_people === offer.required_max_people ? offer.required_min_people : `${offer.required_min_people}–${offer.required_max_people}`}</p>
    {offer.is_near ? <aside className="near-note" aria-label="Нужно подтверждение исключения">
      <strong>Немного выше твоего бюджета</strong>
      {offer.budget_delta !== null ? <span>+{offer.budget_delta} ₽</span> : null}
      <p>Подтверди, если всё равно хочешь присоединиться.</p>
    </aside> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="offer-card__actions">
      <Button variant="primary" loading={busy} disabled={busy} onClick={() => void act(true)}>{offer.is_near ? 'Всё равно впишусь' : 'Я в деле'}</Button>
      <Button variant="secondary" disabled={busy} onClick={() => void act(false)}>{offer.is_near ? 'Пас' : 'Пас'}</Button>
    </div>
    <footer>{offer.is_demo ? 'Демонстрационные данные' : `KudaGo · обновлено ${formatDateTime(offer.source_fetched_at)}`}{offer.source_url ? <a href={offer.source_url} target="_blank" rel="noreferrer">Источник</a> : null}</footer>
  </article>
}
