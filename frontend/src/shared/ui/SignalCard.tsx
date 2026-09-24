import type { Dvizh } from '../../app/api'
import { activityLabel, formatSignalWindow } from '../lib/format'

export function SignalCard({ dvizh }: { dvizh: Dvizh }) {
  return (
    <section className="signal-card" aria-label="Сигнал">
      <p className="signal-card__label">{dvizh.is_initiator ? 'Твой сигнал' : 'Сигнал компании'}</p>
      <p className="signal-card__time">
        {formatSignalWindow(dvizh.available_from, dvizh.available_to)}
      </p>
      <h2>{dvizh.activity_ids.map(activityLabel).join(' или ')}</h2>
      <p className="signal-card__details">
        {dvizh.group_name} · от {dvizh.min_people} до {dvizh.max_people} человек
      </p>
    </section>
  )
}
