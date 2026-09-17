import { Button } from '@maxhub/max-ui'
import type { Plan } from '../../app/api'
import { formatDateTime } from '../../shared/lib/format'

export function PlanCard({ plan }: { plan: Plan }) {
  const share = () => {
    if (window.WebApp?.shareMaxContent) window.WebApp.shareMaxContent({ text: plan.share_text })
    else void navigator.clipboard?.writeText(plan.share_text)
  }
  return <article className="confirmed-plan">
    <div className="confirmed-plan__bolt" aria-hidden="true">ϟ</div>
    <p className="section-kicker">ДВИЖ СОБРАЛСЯ</p>
    <h2>{plan.title}</h2>
    {plan.venue_name ? <p className="confirmed-plan__venue">{plan.venue_name}</p> : null}
    <p>{formatDateTime(plan.starts_at)}{plan.price_text ? <> · {plan.price_text}</> : null}</p>
    <p className="confirmed-plan__people">Уже в деле: {plan.participant_count}</p>
    <div className="confirmed-plan__actions">{plan.source_url ? <Button variant="secondary" onClick={() => window.open(plan.source_url ?? '', '_blank', 'noopener,noreferrer')}>Открыть источник</Button> : null}<Button variant="primary" onClick={share}>Поделиться в MAX</Button></div>
  </article>
}
