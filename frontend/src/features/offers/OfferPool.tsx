import type { Group, Intent, Offer } from '../../app/api'
import { activityLabel, formatPeople, formatSignalWindow, weekDays } from '../../shared/lib/format'
import { Icon } from '../../shared/ui/Icon'
import { PulseMark } from '../../shared/ui/PulseMark'
import type { SignalAdjustment } from '../signals/SignalComposer'
import { OfferCard } from './OfferCard'

export function OfferPool({
  offers,
  group,
  onEdit,
  onInvite,
  onChanged,
  hasActiveSignal = false,
  providerState,
  currentIntent,
  waitingCount = 0,
  onRetry,
  onStop,
}: {
  offers: Offer[]
  group: Group
  onEdit: (adjustment: SignalAdjustment) => void
  onInvite: () => void
  onChanged: () => void
  hasActiveSignal?: boolean
  providerState?: string
  currentIntent?: Intent
  waitingCount?: number
  onRetry?: () => void
  onStop?: () => void
}) {
  const visible = offers.filter(
    (offer) => offer.compatibility_kind !== 'UNVERIFIED' && offer.status === 'PENDING',
  )
  if (!visible.length && !hasActiveSignal)
    return (
      <button type="button" className="home-company-card" onClick={onInvite}>
        <span className="home-company-card__icon" aria-hidden="true">
          <Icon name="users" size={24} />
        </span>
        <span className="home-company-card__content">
          <span className="context-label">Твоя компания</span>
          <strong>{group.name}</strong>
          <span>
            {group.member_count > 1
              ? `${formatPeople(group.member_count)} в компании`
              : 'Пока только ты — можно позвать друзей'}
          </span>
        </span>
        <span className="home-company-card__action">Открыть компанию</span>
      </button>
    )

  if (!visible.length) {
    if (waitingCount)
      return (
        <section className="search-state" aria-live="polite">
          <PulseMark />
          <h1>Ждём ещё участников</h1>
          <p>Подходящий вариант есть. План соберётся, когда подтвердят участие.</p>
          <button type="button" className="primary-button" onClick={onInvite}>
            Позвать друзей
          </button>
          <button type="button" className="text-action" onClick={() => onEdit(null)}>
            Изменить условия
          </button>
        </section>
      )
    if (providerState === 'NO_SOURCE')
      return (
        <section className="search-state">
          <PulseMark />
          <h1>На это время ничего не нашли</h1>
          <p>Попробуй расширить время или выбрать больше категорий.</p>
          {currentIntent?.type === 'ONE_TIME' ? (
            <button type="button" className="primary-button" onClick={() => onEdit('tomorrow')}>
              Добавить завтра
            </button>
          ) : null}
          <button type="button" className="secondary-button" onClick={() => onEdit('any')}>
            Выбрать любые категории
          </button>
          <button type="button" className="text-action" onClick={() => onEdit(null)}>
            Изменить условия
          </button>
        </section>
      )
    if (providerState === 'NO_FEASIBLE_PLAN')
      return (
        <section className="search-state">
          <PulseMark />
          <h1>Пока ничего не совпало</h1>
          <p>Можно немного расширить условия. Другие участники не увидят твои ограничения.</p>
          {currentIntent?.radius_km !== null &&
          currentIntent?.radius_km !== undefined &&
          currentIntent.radius_km < 10 &&
          currentIntent.origin_location_id ? (
            <button type="button" className="primary-button" onClick={() => onEdit('radius')}>
              Увеличить радиус до 10 км
            </button>
          ) : null}
          {currentIntent?.budget_max !== null && currentIntent?.budget_max !== undefined ? (
            <button type="button" className="secondary-button" onClick={() => onEdit('budget')}>
              Разрешить на 200 ₽ дороже
            </button>
          ) : null}
          <button type="button" className="text-action" onClick={() => onEdit(null)}>
            Изменить условия
          </button>
        </section>
      )
    if (providerState === 'PROVIDER_UNAVAILABLE')
      return (
        <section className="search-state" role="alert">
          <h1>Не удалось загрузить варианты</h1>
          <p>Сигнал сохранён. Проверь связь и попробуй ещё раз.</p>
          {onRetry ? (
            <button type="button" className="primary-button" onClick={onRetry}>
              Повторить поиск
            </button>
          ) : null}
          <button type="button" className="text-action" onClick={() => onEdit(null)}>
            Изменить условия
          </button>
        </section>
      )
    return (
      <section className="search-state search-state--searching" aria-live="polite">
        <h1>Ищем подходящий план</h1>
        <p>Проверяем события, места и условия друзей.</p>
        <PulseMark />
        {currentIntent ? (
          <div className="search-state__summary">
            <span>
              <Icon name="calendar" size={17} />
              {currentIntent.type === 'RECURRING'
                ? `Повторяется · ${weekDays(currentIntent.weekdays)}`
                : formatSignalWindow(currentIntent.available_from, currentIntent.available_to)}
            </span>
            <span>
              <Icon name="list" size={17} />
              {currentIntent.activity_categories.map(activityLabel).join(', ')}
            </span>
            {currentIntent.group_name ? (
              <span>
                <Icon name="users" size={17} />
                {currentIntent.group_name}
              </span>
            ) : null}
          </div>
        ) : null}
        <ol className="search-steps">
          <li className="is-done">Сигнал сохранён</li>
          <li className="is-active">Ищем варианты</li>
          <li>Проверяем компанию</li>
        </ol>
        <p className="search-state__note">
          <Icon name="bell" size={22} />
          <span>Можно закрыть приложение — мы пришлём приглашение в MAX.</span>
        </p>
        <button type="button" className="secondary-button" onClick={() => onEdit(null)}>
          Изменить условия
        </button>
        {onStop ? (
          <button type="button" className="search-state__stop" onClick={onStop}>
            Остановить поиск
          </button>
        ) : null}
      </section>
    )
  }

  const dayKey = (date: Date) => date.toDateString()
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  const buckets = [
    { id: 'today', title: 'Сегодня', offers: [] as Offer[] },
    { id: 'tomorrow', title: 'Завтра', offers: [] as Offer[] },
    { id: 'later', title: 'Позже', offers: [] as Offer[] },
  ]
  for (const offer of visible) {
    const key = dayKey(new Date(offer.starts_at))
    const bucket =
      key === dayKey(today) ? buckets[0] : key === dayKey(tomorrow) ? buckets[1] : buckets[2]
    bucket.offers.push(offer)
  }
  return (
    <section className="offer-pool" aria-labelledby="offer-pool-title">
      <div className="section-header">
        <h1 id="offer-pool-title">Приглашения</h1>
        <p>Новые варианты для твоей компании</p>
      </div>
      <div className="offer-day-groups">
        {buckets
          .filter((bucket) => bucket.offers.length)
          .map((bucket) => (
            <section key={bucket.id} aria-labelledby={'offers-' + bucket.id}>
              <h2 id={'offers-' + bucket.id}>{bucket.title}</h2>
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
