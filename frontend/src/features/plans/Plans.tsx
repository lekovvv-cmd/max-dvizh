import type { Plan } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { PlanCard } from './PlanCard'

export function Plans({ plans, onChanged }: { plans: Plan[]; onChanged: () => void }) {
  return (
    <section className="page-stack">
      <h1>Планы</h1>
      {plans.length ? (
        <div className="plans-list plans-list--screen">
          {plans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} onChanged={onChanged} />
          ))}
        </div>
      ) : (
        <EmptyState title="Планов пока нет">
          Когда примешь приглашение, они появятся здесь.
        </EmptyState>
      )}
    </section>
  )
}
