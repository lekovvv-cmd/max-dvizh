import { Button } from '@maxhub/max-ui'
import type { Offer } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { OfferCard } from './OfferCard'

export function OfferPool({ offers, onSignal, onChanged, hasActiveSignal = false, providerState, onRetry }: { offers: Offer[]; onSignal: () => void; onChanged: () => void; hasActiveSignal?: boolean; providerState?: string; onRetry?: () => void }) {
  if (!offers.length) {
    const unavailable = providerState === 'PROVIDER_UNAVAILABLE'
    const noSource = providerState === 'NO_SOURCE'
    const noFeasible = providerState === 'NO_FEASIBLE_PLAN'
    const title = !hasActiveSignal ? 'Сигнала пока нет' : unavailable ? 'Источник сейчас недоступен' : noSource ? 'В это время событий не найдено' : noFeasible ? 'Подходящего плана пока нет' : 'Предложений пока нет'
    const description = !hasActiveSignal ? 'Подай сигнал, когда будешь готов пойти.' : unavailable ? 'Не удалось проверить KudaGo. Сигнал сохранён — попробуй поиск ещё раз.' : noSource ? 'Сигнал сохранён. Попробуй другое время или категории.' : noFeasible ? 'Мы проверили события и места, но твои условия пока не совпали.' : 'Сигнал активен. Когда появится подходящий конкретный план, мы пригласим тебя.'
    return <EmptyState title={title} action={!hasActiveSignal ? { label: 'Подать сигнал ⚡', onClick: onSignal } : onRetry ? { label: 'Повторить поиск', onClick: onRetry } : undefined}>{description}</EmptyState>
  }
  return <section className="offer-pool" aria-labelledby="offer-pool-title">
    <p className="section-kicker">Тебя зовут</p>
    <h1 id="offer-pool-title">Выбери свой ДВИЖ</h1>
    <p className="screen-intro">Все актуальные предложения из твоих компаний — решение всегда за тобой.</p>
    <Button variant="secondary" onClick={onSignal}>Подать сигнал ⚡</Button>
    <div className="offer-list">{offers.map(offer => <OfferCard key={offer.id} offer={offer} onChanged={onChanged} />)}</div>
  </section>
}
