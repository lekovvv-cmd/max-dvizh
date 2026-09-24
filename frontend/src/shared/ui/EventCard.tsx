import type { ReactNode } from 'react'
import type { EventFact } from '../lib/eventFacts'
import { Icon } from './Icon'

export function EventCard({
  id,
  badge,
  title,
  subtitle,
  facts,
  groupName,
  groupSummary,
  groupContent,
  note,
  error,
  primary,
  actions,
  more,
  dialog,
  tone = 'default',
}: {
  id: string
  badge: string
  title: string
  subtitle?: string
  facts: EventFact[]
  groupName: string
  groupSummary?: string
  groupContent?: ReactNode
  note?: ReactNode
  error?: string
  primary?: ReactNode
  actions?: ReactNode
  more?: ReactNode
  dialog?: ReactNode
  tone?: 'default' | 'confirmed' | 'near'
}) {
  return (
    <article id={id} className={'event-card event-card--' + tone}>
      <header
        className={'event-card__poster' + (title.length > 55 ? ' event-card__poster--long' : '')}
      >
        <span className="event-card__badge">{badge}</span>
        <h3>{title}</h3>
        {subtitle ? <p>{subtitle}</p> : null}
      </header>
      {facts.length ? (
        <div className="event-card__facts">
          {facts.map((fact, index) => (
            <div className="event-card__fact" key={fact.icon + index}>
              <Icon name={fact.icon} size={24} />
              <div>
                <strong>{fact.value}</strong>
                {fact.detail ? <span>{fact.detail}</span> : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <div className="event-card__group">
        <div className="event-card__group-title">
          <Icon name="users" size={26} />
          <div>
            <strong>{groupName}</strong>
            {groupSummary ? <span>{groupSummary}</span> : null}
          </div>
        </div>
        {groupContent ? <div className="event-card__group-content">{groupContent}</div> : null}
      </div>
      {note ? <div className="event-card__note">{note}</div> : null}
      {error ? (
        <p className="form-error event-card__error" role="alert">
          {error}
        </p>
      ) : null}
      {primary ? <div className="event-card__primary">{primary}</div> : null}
      {actions ? <div className="event-card__actions">{actions}</div> : null}
      {more ? <div className="event-card__more">{more}</div> : null}
      {dialog}
    </article>
  )
}
