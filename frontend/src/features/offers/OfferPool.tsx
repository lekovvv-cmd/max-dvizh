import type { Offer } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { SectionHeader } from '../../shared/ui/SectionHeader'
import { OfferCard } from './OfferCard'

export function OfferPool({
  offers,
  onSignal,
  onChanged,
  hasActiveSignal = false,
  providerState,
  onRetry,
}: {
  offers: Offer[]
  onSignal: () => void
  onChanged: () => void
  hasActiveSignal?: boolean
  providerState?: string
  onRetry?: () => void
}) {
  if (!offers.length) {
    const unavailable = providerState === 'PROVIDER_UNAVAILABLE'
    const noSource = providerState === 'NO_SOURCE'
    const noFeasible = providerState === 'NO_FEASIBLE_PLAN'
    const title = !hasActiveSignal
      ? 'Сигнала пока нет'
      : unavailable
        ? 'Источник сейчас недоступен'
        : noSource
          ? 'В это время событий не найдено'
          : noFeasible
            ? 'Подходящего плана пока нет'
            : 'Предложений пока нет'
    const description = !hasActiveSignal
      ? 'Сообщи, когда свободен, — мы покажем конкретные варианты.'
      : unavailable
        ? 'Сигнал сохранён. Попробуй поиск ещё раз.'
        : noSource
          ? 'Попробуй другое время или категории.'
          : noFeasible
            ? 'События и места есть, но условия пока не совпали.'
            : 'Когда появится подходящий план, пригласим тебя.'
    return (
      <section className="offer-pool offer-pool--empty">
        <EmptyState
          title={title}
          action={
            !hasActiveSignal
              ? { label: 'Подать сигнал', onClick: onSignal }
              : onRetry
                ? { label: 'Повторить поиск', onClick: onRetry }
                : undefined
          }
        >
          {description}
        </EmptyState>
      </section>
    )
  }
  const dayKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  const buckets = [
    { id: 'today', title: 'Сегодня', offers: [] as Offer[] },
    { id: 'tomorrow', title: 'Завтра', offers: [] as Offer[] },
    { id: 'later', title: 'Позже', offers: [] as Offer[] },
  ]
  for (const offer of offers) {
    const key = dayKey(new Date(offer.starts_at))
    const bucket =
      key === dayKey(today) ? buckets[0] : key === dayKey(tomorrow) ? buckets[1] : buckets[2]
    bucket.offers.push(offer)
  }
  return (
    <section className="offer-pool" aria-labelledby="offer-pool-title">
      <SectionHeader
        id="offer-pool-title"
        title="Приглашения"
        action={
          <button type="button" className="text-action" onClick={onSignal}>
            + Подать сигнал
          </button>
        }
      />
      <div className="offer-day-groups">
        {buckets
          .filter((bucket) => bucket.offers.length)
          .map((bucket) => (
            <section key={bucket.id} aria-labelledby={`offers-${bucket.id}`}>
              <h2 id={`offers-${bucket.id}`}>{bucket.title}</h2>
              <div className="offer-list">
                {bucket.offers.map((offer) => (
                  <OfferCard key={offer.id} offer={offer} onChanged={onChanged} />
                ))}
              </div>
            </section>
          ))}
      </div>
    </section>
  )
}
