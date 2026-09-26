import type { DvizhCandidate } from '../../app/api'
import { formatEventDate } from '../lib/format'

export function ActivityCard({
  candidate,
  status,
  children,
}: {
  candidate: DvizhCandidate
  status?: string
  children?: React.ReactNode
}) {
  return (
    <article className="activity-card">
      {candidate.image_url ? (
        <img className="activity-card__image" src={candidate.image_url} alt="" loading="lazy" />
      ) : (
        <div className="activity-card__art" aria-hidden="true">
          ДВИЖ
        </div>
      )}
      <div className="activity-card__body">
        {status ? <span className="activity-card__status">{status}</span> : null}
        <h2>{candidate.title}</h2>
        {candidate.venue_name && candidate.venue_name !== candidate.title ? (
          <p>{candidate.venue_name}</p>
        ) : null}
        <dl className="activity-card__facts">
          <div>
            <dt>Когда</dt>
            <dd>{formatEventDate(candidate.starts_at)}</dd>
          </div>
          <div>
            <dt>Цена</dt>
            <dd>
              {candidate.price_text || (candidate.price_min === 0 ? 'Бесплатно' : 'Уточни у места')}
            </dd>
          </div>
          {candidate.distance_km !== null ? (
            <div>
              <dt>Расстояние</dt>
              <dd>{candidate.distance_km.toLocaleString('ru-RU')} км</dd>
            </div>
          ) : null}
          {candidate.address_text ? (
            <div>
              <dt>Адрес</dt>
              <dd>{candidate.address_text}</dd>
            </div>
          ) : null}
        </dl>
        {candidate.compatibility === 'NEAR' ? (
          <p className="activity-card__warning">Бюджет выше на {candidate.budget_delta} ₽.</p>
        ) : null}
        {candidate.source_url ? (
          <a href={candidate.source_url} target="_blank" rel="noreferrer">
            Подробнее
          </a>
        ) : null}
        {children}
      </div>
    </article>
  )
}
