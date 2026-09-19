import { Button } from '@maxhub/max-ui'
import { useState } from 'react'
import { api } from '../../app/api'
import type { Plan } from '../../app/api'
import { formatDateTime, formatPeople } from '../../shared/lib/format'
import { DvizhProgress } from '../../shared/ui/DvizhProgress'
import { StatusLabel, type StatusTone } from '../../shared/ui/StatusLabel'

export function PlanCard({ plan, onChanged }: { plan: Plan; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const collecting = plan.status === 'COLLECTING'
  const waitlisted = plan.my_status === 'WAITLISTED'
  const conditional = plan.my_status === 'WAITING_CONDITION'
  const state = waitlisted ? { tone: 'waitlist' as StatusTone, label: 'Лист ожидания' } : conditional ? { tone: 'conditional' as StatusTone, label: 'Ждём ещё людей' } : collecting ? { tone: 'collecting' as StatusTone, label: 'Собираем' } : { tone: 'confirmed' as StatusTone, label: 'ДВИЖ СОБРАЛСЯ' }
  const cancel = async () => { if (!plan.my_offer_id) return; setBusy(true); setError(''); try { await api.cancelAcceptance(plan.my_offer_id); onChanged() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось отменить участие') } finally { setBusy(false) } }
  const share = () => {
    if (window.WebApp?.shareMaxContent) window.WebApp.shareMaxContent({ text: plan.share_text })
    else void navigator.clipboard?.writeText(plan.share_text)
  }
  const progressCurrent = conditional && plan.personal_response_count !== null ? plan.personal_response_count : plan.participant_count
  const progressTarget = conditional && plan.personal_required_min !== null ? plan.personal_required_min : plan.required_min_people
  const progressLabel = waitlisted ? 'Если освободится место, сообщим' : conditional && plan.personal_required_min !== null && plan.personal_response_count !== null ? `Твоё условие: ${formatPeople(plan.personal_required_min)} · сейчас готовы ${plan.personal_response_count}` : collecting ? `${plan.participant_count} из ${plan.required_min_people} · ${plan.remaining_to_confirm === 1 ? 'нужен' : 'нужно'} ещё ${plan.remaining_to_confirm}` : `${plan.participant_count} в деле${plan.remaining_capacity > 0 ? ' · можно присоединиться' : ''}`
  return <article id={`plan-${plan.id}`} className={`plan-card plan-card--${state.tone}`}>
    <StatusLabel tone={state.tone}>{state.label}</StatusLabel>
    <div className="plan-card__title"><h2>{plan.title}</h2><span className="context-label">{plan.group_name}</span></div>
    {plan.venue_name ? <p className="plan-card__venue">{plan.venue_name}</p> : null}
    {plan.address_text ? <p>{plan.address_text}</p> : null}
    <p>{formatDateTime(plan.starts_at)}{plan.price_text ? <> · {plan.price_text}</> : null}</p>
    {plan.price_kind === 'FROM' ? <p className="inline-caveat">Цена может быть выше</p> : null}
    {plan.opening_hours_unverified ? <p className="inline-caveat">Режим работы лучше проверить</p> : null}
    {!waitlisted ? <DvizhProgress current={progressCurrent} target={progressTarget} label={progressLabel} /> : <p className="plan-card__note">{progressLabel}</p>}
    {!collecting && plan.participants.length ? <p className="plan-card__participants">{plan.participants.map(person => person.display_name).join(', ')}</p> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="plan-card__actions">{plan.source_url ? <Button variant="secondary" onClick={() => window.open(plan.source_url ?? '', '_blank', 'noopener,noreferrer')}>Источник</Button> : null}{!collecting && !waitlisted && !conditional ? <Button variant="primary" onClick={share}>Поделиться</Button> : null}{plan.my_offer_id ? <button type="button" className="text-action text-action--danger" disabled={busy} onClick={() => void cancel()}>{busy ? 'Отменяем…' : 'Передумал'}</button> : null}</div>
  </article>
}
