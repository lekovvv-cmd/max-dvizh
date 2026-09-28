import { useState } from 'react'
import type { DvizhCandidate } from '../../app/api'
import { formatEventDate } from '../lib/format'
import { Icon } from './Icon'

function detailsUrl(candidate: DvizhCandidate) {
  if (candidate.source_url && /^https?:\/\//i.test(candidate.source_url)) {
    return candidate.source_url
  }

  const mapCoordinates = candidate.image_url?.match(
    /^\/api\/v1\/place-map\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)\//,
  )
  if (mapCoordinates) {
    const [, latitude, longitude] = mapCoordinates
    return `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=17/${latitude}/${longitude}`
  }

  const query = [candidate.title, candidate.address_text].filter(Boolean).join(', ')
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(query)}`
}

export function ActivityCard({
  candidate,
  status,
  children,
}: {
  candidate: DvizhCandidate
  status?: string
  children?: React.ReactNode
}) {
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null)
  const imageUrl = candidate.image_url === failedImageUrl ? null : candidate.image_url
  const isMap = imageUrl?.startsWith('/api/v1/place-map/')
  return (
    <article className="activity-card">
      <div className="activity-card__visual">
        {imageUrl ? (
          <img
            className="activity-card__image"
            src={imageUrl}
            alt={isMap ? `Место «${candidate.title}» на карте` : ''}
            loading="lazy"
            onError={() => setFailedImageUrl(imageUrl)}
          />
        ) : (
          <div className="activity-card__art" aria-hidden="true">
            ДВИЖ
          </div>
        )}
        {isMap ? <span className="activity-card__map-label">На карте</span> : null}
      </div>
      <div className="activity-card__body">
        {status ? <span className="activity-card__status">{status}</span> : null}
        <h2>{candidate.title}</h2>
        {candidate.venue_name && candidate.venue_name !== candidate.title ? (
          <p className="activity-card__venue">{candidate.venue_name}</p>
        ) : null}
        <dl className="activity-card__facts">
          <div>
            <dt className="visually-hidden">Когда</dt>
            <dd>
              <Icon name="calendar" size={16} />
              {formatEventDate(candidate.starts_at)}
            </dd>
          </div>
          {candidate.address_text ? (
            <div>
              <dt className="visually-hidden">Адрес</dt>
              <dd>
                <Icon name="pin" size={16} />
                {candidate.address_text}
                {candidate.distance_km !== null
                  ? ` · ${candidate.distance_km.toLocaleString('ru-RU')} км`
                  : null}
              </dd>
            </div>
          ) : candidate.distance_km !== null ? (
            <div>
              <dt className="visually-hidden">Расстояние</dt>
              <dd>
                <Icon name="route" size={16} />
                {candidate.distance_km.toLocaleString('ru-RU')} км
              </dd>
            </div>
          ) : null}
          <div>
            <dt className="visually-hidden">Цена</dt>
            <dd>
              <Icon name="money" size={16} />
              {candidate.price_text ||
                (candidate.price_min === 0
                  ? 'Бесплатно'
                  : candidate.price_min !== null
                    ? `от ${candidate.price_min.toLocaleString('ru-RU')} ₽`
                    : 'Уточни у места')}
            </dd>
          </div>
        </dl>
        {candidate.compatibility === 'NEAR' ? (
          <p className="activity-card__warning">Бюджет выше на {candidate.budget_delta} ₽.</p>
        ) : null}
        <a
          className="activity-card__details"
          href={detailsUrl(candidate)}
          target="_blank"
          rel="noopener noreferrer"
        >
          Подробнее о месте <Icon name="chevron" size={16} />
        </a>
        {children}
      </div>
    </article>
  )
}
