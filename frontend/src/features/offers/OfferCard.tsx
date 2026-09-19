import { Button } from '@maxhub/max-ui'
import { useState } from 'react'

import { api } from '../../app/api'
import type { Offer } from '../../app/api'
import { formatDateTime, formatTime } from '../../shared/lib/format'
import { DvizhProgress } from '../../shared/ui/DvizhProgress'
import { StatusLabel } from '../../shared/ui/StatusLabel'

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
  const progressLabel = offer.remaining_to_confirm > 0 ? `${offer.accepted_count} из ${offer.required_min_people} · нужен ещё ${offer.remaining_to_confirm}` : offer.remaining_capacity > 0 ? `${offer.accepted_count} в деле · можно присоединиться` : `${offer.accepted_count} из ${offer.effective_max} · мест нет`
  const progressTarget = offer.remaining_to_confirm > 0 ? offer.required_min_people : offer.effective_max
  return <article id={`offer-${offer.id}`} className={`offer-card ${offer.is_near ? 'offer-card--near' : ''}`}>
    <div className="offer-card__head"><span className="context-label">{offer.group_name}</span>{offer.is_demo ? <span className="demo-mark">Демо</span> : null}</div>
    <div className="offer-card__title"><h3>{offer.title}</h3>{offer.is_near ? <StatusLabel tone="conditional">Чуть дороже</StatusLabel> : null}</div>
    <p className="offer-card__when">{formatDateTime(offer.starts_at)}–{formatTime(offer.ends_at)}</p>
    {offer.venue_name ? <p className="offer-card__venue">{offer.venue_name}</p> : null}
    {offer.address_text ? <p>{offer.address_text}</p> : null}
    {hasDetails ? <p className="offer-card__details">{offer.price_text}{offer.price_text && offer.distance_km !== null ? ' · ' : null}{offer.distance_km !== null ? `${offer.distance_km.toFixed(1)} км` : null}</p> : null}
    {offer.price_kind === 'FROM' ? <p className="inline-caveat">Цена может быть выше</p> : null}
    {offer.opening_hours_unverified ? <p className="inline-caveat">Режим работы лучше проверить</p> : null}
    <DvizhProgress current={offer.accepted_count} target={progressTarget} label={progressLabel} />
    {offer.is_near ? <aside className="near-note" aria-label="Нужно подтверждение исключения">
      <strong>{offer.budget_delta !== null ? `На ${offer.budget_delta} ₽ выше твоего лимита` : 'Немного выше твоего лимита'}</strong>
      <p>Нужно подтвердить отдельно.</p>
    </aside> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="offer-card__actions">
      {offer.can_accept || offer.can_waitlist ? <Button variant="primary" loading={busy} disabled={busy} onClick={() => void act(true)}>{offer.can_waitlist ? 'Встать в лист ожидания' : offer.is_near ? 'Всё равно впишусь' : 'Я в деле'}</Button> : null}
      <Button variant="secondary" disabled={busy} onClick={() => void act(false)}>Пас</Button>
    </div>
    <footer>{offer.is_demo ? 'Демонстрационные данные' : `KudaGo · ${formatDateTime(offer.source_fetched_at)}`}{offer.source_url ? <a href={offer.source_url} target="_blank" rel="noreferrer">Источник</a> : null}</footer>
  </article>
}
