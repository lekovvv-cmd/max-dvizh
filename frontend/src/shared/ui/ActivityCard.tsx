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
  if (candidate.latitude != null && candidate.longitude != null) {
    return `https://www.openstreetmap.org/?mlat=${candidate.latitude}&mlon=${candidate.longitude}#map=17/${candidate.latitude}/${candidate.longitude}`
  }
  if (mapCoordinates) {
    const [, latitude, longitude] = mapCoordinates
    return `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=17/${latitude}/${longitude}`
  }

  const query = [candidate.title, candidate.address_text].filter(Boolean).join(', ')
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(query)}`
}

function mapEmbedUrl(latitude: number, longitude: number) {
  const delta = 0.006
  const bounds = [longitude - delta, latitude - delta, longitude + delta, latitude + delta]
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bounds.join('%2C')}&layer=mapnik&marker=${latitude}%2C${longitude}`
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
  const fallbackCoordinates = candidate.image_url?.match(
    /^\/api\/v1\/place-map\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)\//,
  )
  const latitude =
    candidate.latitude ?? (fallbackCoordinates ? Number(fallbackCoordinates[1]) : null)
  const longitude =
    candidate.longitude ?? (fallbackCoordinates ? Number(fallbackCoordinates[2]) : null)
  const showMap = !imageUrl && latitude != null && longitude != null
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
        ) : showMap ? (
          <iframe
            className="activity-card__map"
            src={mapEmbedUrl(latitude, longitude)}
            title={`Место «${candidate.title}» на карте`}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="activity-card__art" aria-hidden="true">
            <Icon name="pin" size={32} />
            <span>Фото нет</span>
          </div>
        )}
        {isMap || showMap ? <span className="activity-card__map-label">На карте</span> : null}
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
