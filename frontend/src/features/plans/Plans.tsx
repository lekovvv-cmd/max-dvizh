import type { Plan } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { PlanCard } from './PlanCard'

export function Plans({ plans, onChanged }: { plans: Plan[]; onChanged: () => void }) {
  return <section><h1>Ближайшие ДВИЖи</h1>{plans.length ? <div className="plans-list">{plans.map(plan => <PlanCard key={plan.id} plan={plan} onChanged={onChanged} />)}</div> : <EmptyState title="Планов пока нет">Когда откликнешься на предложение, здесь появится план.</EmptyState>}</section>
}
