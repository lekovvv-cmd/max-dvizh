import type { Dvizh } from '../../app/api'
import { activityLabel, formatSignalWindow } from '../lib/format'
import { dvizhStatusLabel } from '../lib/dvizhStatus'

export function DvizhCard({ dvizh, onOpen }: { dvizh: Dvizh; onOpen: () => void }) {
  const gathered = dvizh.status === 'GATHERED'
  const title = gathered
    ? dvizh.candidates.find((candidate) => candidate.id === dvizh.active_candidate_id)?.title
    : null

  return (
    <button type="button" className="dvizh-card" onClick={onOpen}>
      <span className="dvizh-card__content">
        <strong>{title || dvizh.activity_ids.map(activityLabel).join(' или ')}</strong>
        <span className="dvizh-card__meta">
          {formatSignalWindow(dvizh.available_from, dvizh.available_to)} · {dvizh.group_name}
        </span>
      </span>
      <span className="dvizh-card__action">
        <span className={'dvizh-card__status' + (gathered ? ' dvizh-card__status--gathered' : '')}>
          {dvizhStatusLabel(dvizh)}
        </span>
      </span>
    </button>
  )
}
