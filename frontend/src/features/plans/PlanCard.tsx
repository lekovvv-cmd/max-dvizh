import { Button } from '@maxhub/max-ui'
import { useState } from 'react'
import { api } from '../../app/api'
import type { Plan } from '../../app/api'
import { formatDateTime } from '../../shared/lib/format'

export function PlanCard({ plan, onChanged }: { plan: Plan; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const collecting = plan.status === 'COLLECTING'
  const waitlisted = plan.my_status === 'WAITLISTED'
  const conditional = plan.my_status === 'WAITING_CONDITION'
  const cancel = async () => { if (!plan.my_offer_id) return; setBusy(true); setError(''); try { await api.cancelAcceptance(plan.my_offer_id); onChanged() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось отменить участие') } finally { setBusy(false) } }
  const share = () => {
    if (window.WebApp?.shareMaxContent) window.WebApp.shareMaxContent({ text: plan.share_text })
    else void navigator.clipboard?.writeText(plan.share_text)
  }
  return <article id={`plan-${plan.id}`} className="confirmed-plan">
    <div className="confirmed-plan__bolt" aria-hidden="true">ϟ</div>
    <p className="section-kicker">{waitlisted ? 'Ты в листе ожидания' : conditional ? 'Ждём твоё условие' : collecting ? 'Собираем' : 'ДВИЖ СОБРАЛСЯ'}</p>
    <h2>{plan.title}</h2>
    <span className="group-chip">{plan.group_name}</span>
    {plan.venue_name ? <p className="confirmed-plan__venue">{plan.venue_name}</p> : null}
    {plan.address_text ? <p>{plan.address_text}</p> : null}
    <p>{formatDateTime(plan.starts_at)}{plan.price_text ? <> · {plan.price_text}</> : null}</p>
    {plan.price_kind === 'FROM' ? <p>Итоговая цена может быть выше</p> : null}
    {plan.opening_hours_unverified ? <p>Режим работы лучше проверить по ссылке источника</p> : null}
    <p className="confirmed-plan__people">{waitlisted ? 'Если место освободится до начала, мы сообщим тебе' : conditional && plan.personal_required_min !== null && plan.personal_response_count !== null ? `Ты присоединишься, если соберётся ${plan.personal_required_min}. Сейчас ${plan.personal_response_count} из ${plan.personal_required_min}${plan.personal_response_count < plan.personal_required_min ? ` · нужно ещё ${plan.personal_required_min - plan.personal_response_count}` : ''}` : collecting ? `${plan.participant_count} из ${plan.required_min_people} · нужен ещё ${plan.remaining_to_confirm}` : `${plan.participant_count} в деле${plan.remaining_capacity > 0 ? ' · можно присоединиться' : ''}`}</p>
    {!collecting && plan.participants.length ? <p>{plan.participants.map(person => person.display_name).join(', ')}</p> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="confirmed-plan__actions">{plan.source_url ? <Button variant="secondary" onClick={() => window.open(plan.source_url ?? '', '_blank', 'noopener,noreferrer')}>Открыть источник</Button> : null}{!collecting && !waitlisted && !conditional ? <Button variant="primary" onClick={share}>Поделиться</Button> : null}{plan.my_offer_id ? <Button variant="secondary" loading={busy} disabled={busy} onClick={() => void cancel()}>Передумал</Button> : null}</div>
  </article>
}
