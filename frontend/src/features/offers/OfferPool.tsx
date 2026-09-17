import type { Offer } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { OfferCard } from './OfferCard'

export function OfferPool({ offers, onSignal, onChanged }: { offers: Offer[]; onSignal: () => void; onChanged: () => void }) {
  if (!offers.length) return <EmptyState title="Пока тихо" action={{ label: 'Подать сигнал ⚡', onClick: onSignal }}>Подай сигнал — ДВИЖ сам найдёт варианты, которые подходят вашей компании.</EmptyState>
  return <section className="offer-pool" aria-labelledby="offer-pool-title">
    <p className="section-kicker">Тебя зовут</p>
    <h1 id="offer-pool-title">Выбери свой ДВИЖ</h1>
    <p className="screen-intro">Все актуальные предложения из твоих компаний — решение всегда за тобой.</p>
    <div className="offer-list">{offers.map(offer => <OfferCard key={offer.id} offer={offer} onChanged={onChanged} />)}</div>
  </section>
}
