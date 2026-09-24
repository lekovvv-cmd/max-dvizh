import { useRef, useState } from 'react'
import { api } from '../../app/api'
import type { Offer } from '../../app/api'
import { eventFacts } from '../../shared/lib/eventFacts'
import { formatPeopleNeeded } from '../../shared/lib/format'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { DvizhProgress } from '../../shared/ui/DvizhProgress'
import { EventCard } from '../../shared/ui/EventCard'
import { Icon } from '../../shared/ui/Icon'

export function OfferCard({ offer, onChanged }: { offer: Offer; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [error, setError] = useState('')
  const [details, setDetails] = useState(false)
  const [nearOpen, setNearOpen] = useState(false)
  const [accepted, setAccepted] = useState(false)

  async function act(accept: boolean) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError('')
    try {
      if (accept) {
        await api.accept(offer.id, offer.is_near)
        setAccepted(true)
      } else await api.reject(offer.id)
      setNearOpen(false)
      onChanged()
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Не удалось сохранить выбор. Попробуй ещё раз.',
      )
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }

  const progress =
    offer.remaining_to_confirm > 0
      ? offer.accepted_count + ' из ' + offer.required_min_people + ' подтвердили'
      : offer.accepted_count + ' готовы'
  const facts = eventFacts(offer)
  if (accepted)
    return (
      <EventCard
        id={'offer-' + offer.id}
        badge="Ты в деле"
        title={offer.title}
        subtitle="Ждём подтверждения остальных."
        facts={facts}
        groupName={offer.group_name}
        groupContent={
          <DvizhProgress
            current={offer.accepted_count + 1}
            target={offer.required_min_people}
            label={offer.accepted_count + 1 + ' из ' + offer.required_min_people + ' подтвердили'}
          />
        }
      />
    )
  return (
    <EventCard
      id={'offer-' + offer.id}
      badge="Есть вариант!"
      title={offer.title}
      subtitle={'Для компании «' + offer.group_name + '»'}
      facts={facts}
      groupName={offer.group_name}
      groupSummary={progress}
      groupContent={
        <DvizhProgress
          current={offer.accepted_count}
          target={offer.required_min_people}
          label={
            offer.remaining_to_confirm > 0
              ? formatPeopleNeeded(offer.remaining_to_confirm)
              : 'Компания готова собраться.'
          }
        />
      }
      tone={offer.is_near ? 'near' : 'default'}
      note={
        offer.is_near ? (
          <p className="near-note">
            {offer.budget_delta !== null
              ? 'На ' + offer.budget_delta.toLocaleString('ru-RU') + ' ₽ дороже твоего бюджета.'
              : 'Этот вариант выходит за твой бюджет.'}
          </p>
        ) : undefined
      }
      error={error}
      primary={
        offer.can_accept || offer.can_waitlist ? (
          <button
            type="button"
            className="primary-button event-card__accept"
            disabled={busy}
            onClick={() => (offer.is_near ? setNearOpen(true) : void act(true))}
          >
            <span>{busy ? 'Сохраняем…' : offer.can_waitlist ? 'В лист ожидания' : 'Я пойду'}</span>
            <Icon name="arrowRight" size={24} />
          </button>
        ) : undefined
      }
      actions={
        <>
          <button
            type="button"
            className="event-card__action"
            aria-expanded={details}
            onClick={() => setDetails((value) => !value)}
          >
            <Icon name="document" size={22} />
            Подробнее
          </button>
          <button
            type="button"
            className="event-card__action"
            disabled={busy}
            onClick={() => void act(false)}
          >
            <Icon name="ban" size={22} />
            Не подходит
          </button>
        </>
      }
      more={
        details ? (
          <>
            {offer.address_text ? <p>{offer.address_text}</p> : null}
            {offer.price_kind === 'FROM' ? <p>Цена может быть выше.</p> : null}
            {offer.opening_hours_unverified ? <p>Режим работы лучше проверить.</p> : null}
            {offer.source_url ? (
              <a
                className="event-card__source"
                href={offer.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Страница события
              </a>
            ) : null}
            {!offer.address_text && !offer.source_url ? <p>Других подробностей пока нет.</p> : null}
          </>
        ) : undefined
      }
      dialog={
        nearOpen ? (
          <ConfirmDialog
            title="Подтвердить этот вариант?"
            description={
              offer.budget_delta !== null
                ? 'Он на ' +
                  offer.budget_delta.toLocaleString('ru-RU') +
                  ' ₽ дороже твоего бюджета.'
                : 'Он выходит за твой бюджет.'
            }
            confirmLabel="Всё равно пойду"
            cancelLabel="Вернуться"
            busy={busy}
            onConfirm={() => void act(true)}
            onCancel={() => setNearOpen(false)}
          />
        ) : undefined
      }
    />
  )
}
