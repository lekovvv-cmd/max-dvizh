import type { Group, Intent } from '../../app/api'
import { activityLabel, formatSignalWindow } from '../../shared/lib/format'
import { StatusLabel } from '../../shared/ui/StatusLabel'

export function ActiveSignalSummary({
  batch,
  groups,
  status,
  onEdit,
  onCancel,
}: {
  batch: Intent[]
  groups: Group[]
  status: string
  onEdit: () => void
  onCancel: () => void
}) {
  const first = batch[0]
  const companyNames = batch
    .map((item) => item.group_name || groups.find((group) => group.id === item.group_id)?.name)
    .filter(Boolean)
    .join(' + ')
  const constraints = [
    first.budget_max !== null ? `до ${first.budget_max} ₽` : null,
    first.radius_km !== null ? `${first.radius_km} км` : null,
  ].filter(Boolean)

  return (
    <article className="active-signal">
      <StatusLabel>{status}</StatusLabel>
      <p className="active-signal__time">
        {formatSignalWindow(first.available_from, first.available_to)}
      </p>
      <p>{first.activity_categories.map(activityLabel).join(', ')}</p>
      <p className="text-muted">
        {companyNames}
        {constraints.length ? ` · ${constraints.join(' · ')}` : ''}
      </p>
      <div className="inline-actions">
        <button type="button" className="text-action" onClick={onEdit}>
          Изменить
        </button>
        <button type="button" className="text-action text-action--danger" onClick={onCancel}>
          Остановить
        </button>
      </div>
    </article>
  )
}
