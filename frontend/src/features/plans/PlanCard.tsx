import { useState } from 'react'
import { api } from '../../app/api'
import type { Plan } from '../../app/api'
import { eventFacts } from '../../shared/lib/eventFacts'
import { formatPeople } from '../../shared/lib/format'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { DvizhProgress } from '../../shared/ui/DvizhProgress'
import { EventCard } from '../../shared/ui/EventCard'
import { Icon } from '../../shared/ui/Icon'

export function PlanCard({ plan, onChanged }: { plan: Plan; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cancelOpen, setCancelOpen] = useState(false)
  const [shared, setShared] = useState(false)
  const collecting = plan.status === 'COLLECTING'
  const conditional = plan.my_status === 'WAITING_CONDITION'
  const waitlisted = plan.my_status === 'WAITLISTED'
  const confirmed = plan.status.startsWith('CONFIRMED') && !conditional

  async function cancel() {
    if (!plan.my_offer_id || busy) return
    setBusy(true)
    setError('')
    try {
      await api.cancelAcceptance(plan.my_offer_id)
      setCancelOpen(false)
      onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось отменить участие.')
    } finally {
      setBusy(false)
    }
  }

  async function share() {
    try {
      if (window.WebApp?.shareMaxContent) window.WebApp.shareMaxContent({ text: plan.share_text })
      else {
        await navigator.clipboard.writeText(plan.share_text)
        setShared(true)
      }
    } catch {
      setError('Не удалось поделиться. Попробуй ещё раз.')
    }
  }

  const progressCurrent =
    conditional && plan.personal_response_count !== null
      ? plan.personal_response_count
      : plan.participant_count
  const progressTarget =
    conditional && plan.personal_required_min !== null
      ? plan.personal_required_min
      : plan.required_min_people
  const progressLabel = waitlisted
    ? 'Если освободится место, сообщим.'
    : conditional && plan.personal_required_min !== null && plan.personal_response_count !== null
      ? 'Твоё условие: ' +
        plan.personal_response_count +
        ' из ' +
        plan.personal_required_min +
        ' готовы'
      : collecting
        ? plan.participant_count + ' из ' + plan.required_min_people + ' подтвердили'
        : 'Пойдут ' + formatPeople(plan.participant_count)

  const facts = eventFacts(plan)

  return (
    <EventCard
      id={'plan-' + plan.id}
      badge={
        confirmed
          ? 'ДВИЖ собрался'
          : conditional
            ? 'Ждём твоё условие'
            : waitlisted
              ? 'Лист ожидания'
              : 'Ты в деле'
      }
      title={plan.title}
      subtitle={'Для компании «' + plan.group_name + '»'}
      facts={facts}
      groupName={plan.group_name}
      groupSummary={waitlisted ? progressLabel : undefined}
      groupContent={
        waitlisted ? undefined : confirmed && plan.participants.length ? (
          <div className="event-card__participants">
            <strong>С вами пойдут</strong>
            <div className="event-card__avatars" aria-hidden="true">
              {plan.participants.slice(0, 5).map((person) => (
                <span key={person.id}>{person.display_name.trim().slice(0, 1).toUpperCase()}</span>
              ))}
            </div>
            <p>{plan.participants.map((person) => person.display_name).join(', ')}</p>
          </div>
        ) : (
          <DvizhProgress current={progressCurrent} target={progressTarget} label={progressLabel} />
        )
      }
      tone={confirmed ? 'confirmed' : 'default'}
      note={
        plan.opening_hours_unverified ? (
          <p className="inline-caveat">Режим работы лучше проверить.</p>
        ) : undefined
      }
      error={error}
      primary={
        confirmed && plan.source_url ? (
          <a
            className="primary-button event-card__accept"
            href={plan.source_url}
            target="_blank"
            rel="noreferrer"
          >
            <span>Подробнее о плане</span>
            <Icon name="arrowRight" size={23} />
          </a>
        ) : undefined
      }
      actions={
        confirmed || plan.my_offer_id ? (
          <>
            {confirmed ? (
              <button
                type="button"
                className={
                  plan.source_url
                    ? 'event-card__action'
                    : 'primary-button event-card__action--primary'
                }
                onClick={() => void share()}
              >
                <Icon name="share" size={20} />
                {window.WebApp?.shareMaxContent
                  ? 'Поделиться'
                  : shared
                    ? 'Скопировано'
                    : 'Скопировать'}
              </button>
            ) : null}
            {plan.my_offer_id ? (
              <button
                type="button"
                className="event-card__action"
                onClick={() => setCancelOpen(true)}
              >
                <Icon name="ban" size={20} /> Не смогу пойти
              </button>
            ) : null}
          </>
        ) : undefined
      }
      dialog={
        cancelOpen ? (
          <ConfirmDialog
            title="Отменить участие?"
            description="Другие участники увидят, что план снова собирается."
            confirmLabel="Отменить участие"
            cancelLabel="Остаться"
            busy={busy}
            onConfirm={() => void cancel()}
            onCancel={() => setCancelOpen(false)}
          />
        ) : undefined
      }
    />
  )
}
