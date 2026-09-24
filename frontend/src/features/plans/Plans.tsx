import type { Plan } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { PlanCard } from './PlanCard'

export function Plans({
  plans,
  onChanged,
  onSignal,
}: {
  plans: Plan[]
  onChanged: () => void
  onSignal: () => void
}) {
  const readyPlans = plans.filter((plan) => plan.status.startsWith('CONFIRMED'))
  const collectingPlans = plans.filter((plan) => plan.status === 'COLLECTING')
  const showSections = readyPlans.length > 0 && collectingPlans.length > 0
  return (
    <section className="page-stack">
      <h1>Планы</h1>
      {readyPlans.length || collectingPlans.length ? (
        <div className="plans-list plans-list--screen">
          {showSections ? <h2>Готовые</h2> : null}
          {readyPlans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} onChanged={onChanged} />
          ))}
          {showSections ? <h2>Собираются</h2> : null}
          {collectingPlans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} onChanged={onChanged} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="Пока нет готовых планов"
          action={{ label: 'Подать сигнал', onClick: onSignal }}
        >
          Подай сигнал — ДВИЖ найдёт вариант для компании.
        </EmptyState>
      )}
    </section>
  )
}
