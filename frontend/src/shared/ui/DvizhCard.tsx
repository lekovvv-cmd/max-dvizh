import type { Dvizh } from '../../app/api'
import { activityLabel, formatSignalWindow } from '../lib/format'
import { dvizhStatusLabel } from '../lib/dvizhStatus'
import { Icon } from './Icon'

export function DvizhCard({ dvizh, onOpen }: { dvizh: Dvizh; onOpen: () => void }) {
  const gathered = dvizh.status === 'GATHERED'
  const title = gathered
    ? dvizh.candidates.find((candidate) => candidate.id === dvizh.active_candidate_id)?.title
    : null

  return (
    <button type="button" className="dvizh-card" onClick={onOpen}>
      <span className="dvizh-card__top">
        <span className={'dvizh-card__status' + (gathered ? ' dvizh-card__status--gathered' : '')}>
          <span className="dvizh-card__status-dot" aria-hidden="true" />
          {dvizhStatusLabel(dvizh)}
        </span>
        <Icon name="arrowRight" size={19} />
      </span>
      <strong>{title || dvizh.activity_ids.map(activityLabel).join(' или ')}</strong>
      <span className="dvizh-card__meta">
        <span>
          <Icon name="calendar" size={16} />
          {formatSignalWindow(dvizh.available_from, dvizh.available_to)}
        </span>
        <span>
          <Icon name="users" size={16} />
          {dvizh.group_name}
        </span>
      </span>
    </button>
  )
}
