import type { Plan } from '../../app/api'
import { EmptyState } from '../../shared/ui/EmptyState'
import { PlanCard } from './PlanCard'

export function Plans({ plans }: { plans: Plan[] }) {
  return <section><p className="section-kicker">Твои планы</p><h1>Ближайшие ДВИЖи</h1>{plans.length ? <div className="plans-list">{plans.map(plan => <PlanCard key={plan.id} plan={plan} />)}</div> : <EmptyState title="Планов пока нет">Как только нужное число людей подтвердит участие, здесь появится собравшийся ДВИЖ.</EmptyState>}</section>
}
