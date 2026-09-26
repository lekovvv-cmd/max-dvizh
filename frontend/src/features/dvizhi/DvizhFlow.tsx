import { useRef, useState } from 'react'

import { api, type Dvizh, type DvizhCandidate } from '../../app/api'
import { formatPeople } from '../../shared/lib/format'
import { dvizhStatusLabel } from '../../shared/lib/dvizhStatus'
import { ActivityCard } from '../../shared/ui/ActivityCard'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { SignalCard } from '../../shared/ui/SignalCard'

const ROUND_SIZE = 8

export function DvizhFlow({
  dvizh,
  onUpdate,
  onEdit,
  onNew,
}: {
  dvizh: Dvizh
  onUpdate: (value: Dvizh) => void
  onEdit: () => void
  onNew: () => void
}) {
  const [limit, setLimit] = useState(ROUND_SIZE)
  const [drag, setDrag] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [placeOpen, setPlaceOpen] = useState(false)
  const [placeQuery, setPlaceQuery] = useState('')
  const [selectionFinished, setSelectionFinished] = useState(false)
  const [nearConsent, setNearConsent] = useState<{
    candidate: DvizhCandidate
    action: 'react' | 'confirm'
  } | null>(null)
  const startX = useRef<number | null>(null)
  const dragX = useRef(0)
  const busyRef = useRef(false)
  const choosing = dvizh.status === 'CHOOSING_CANDIDATES'
  const reviewing =
    dvizh.status === 'COLLECTING_REACTIONS' || dvizh.status === 'AWAITING_CONFIRMATION'
  const stack =
    choosing || (reviewing && !dvizh.is_initiator)
      ? dvizh.candidates.slice(0, choosing ? limit : undefined)
      : []
  const pending = stack.filter(
    (candidate) =>
      candidate.compatibility !== 'UNVERIFIED' &&
      !candidate.my_reaction &&
      new Date(candidate.expires_at) > new Date(),
  )
  const current =
    dvizh.status === 'AWAITING_CONFIRMATION' || selectionFinished ? undefined : pending[0]
  const actionableCount = stack.filter(
    (candidate) => candidate.compatibility !== 'UNVERIFIED',
  ).length
  const answered = actionableCount - pending.length
  const match = dvizh.candidates.find((candidate) => candidate.id === dvizh.active_candidate_id)

  async function act(
    action: () => Promise<Dvizh>,
    failure = 'Не удалось сохранить. Попробуй ещё раз.',
  ) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError('')
    try {
      onUpdate(await action())
    } catch (reason) {
      setError(
        reason instanceof Error &&
          ['Не нашли это место.', 'Это место не подошло по условиям.'].includes(reason.message)
          ? reason.message
          : failure,
      )
    } finally {
      busyRef.current = false
      setBusy(false)
      setDrag(0)
      dragX.current = 0
    }
  }

  function react(candidate: DvizhCandidate, value: 'WOULD_GO' | 'PASS') {
    const near = value === 'WOULD_GO' && candidate.compatibility === 'NEAR'
    if (near) {
      setNearConsent({ candidate, action: 'react' })
      setDrag(0)
      dragX.current = 0
      return
    }
    void act(() => api.react(dvizh.id, candidate.id, value, false), 'Этот вариант уже недоступен.')
  }

  const placeRule = new Intl.PluralRules('ru-RU').select(dvizh.chosen_count)
  const placeNoun = placeRule === 'one' ? 'место' : placeRule === 'few' ? 'места' : 'мест'
  const doneChoosing = choosing && !current
  const needsConfirm = dvizh.status === 'AWAITING_CONFIRMATION' && match?.my_reaction === 'WOULD_GO'
  const waitlisted = dvizh.my_confirmation === 'WAITLISTED'
  const waitlistAction =
    waitlisted && match ? (
      <div className="dvizh-result">
        <p>Ты в листе ожидания.</p>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() =>
            match.compatibility === 'NEAR'
              ? setNearConsent({ candidate: match, action: 'confirm' })
              : void act(
                  () => api.confirmDvizh(dvizh.id, match.id, false),
                  'Этот вариант уже недоступен.',
                )
          }
        >
          Проверить место
        </button>
      </div>
    ) : null
  const placeSearch =
    dvizh.is_initiator &&
    (choosing || ['NO_SOURCE', 'PROVIDER_UNAVAILABLE'].includes(dvizh.status)) ? (
      <div className="place-search">
        <button
          type="button"
          className="text-action"
          aria-expanded={placeOpen}
          onClick={() => setPlaceOpen((value) => !value)}
        >
          Знаешь конкретное место?
        </button>
        {placeOpen ? (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (placeQuery.trim().length >= 2)
                void act(async () => {
                  try {
                    return await api.searchPlace(dvizh.id, placeQuery.trim())
                  } catch (reason) {
                    const message = reason instanceof Error ? reason.message : ''
                    throw new Error(
                      /не подходит/i.test(message)
                        ? 'Это место не подошло по условиям.'
                        : /не нашли/i.test(message)
                          ? 'Не нашли это место.'
                          : 'Не удалось загрузить варианты.',
                    )
                  }
                }, 'Не удалось загрузить варианты.')
            }}
          >
            <label>
              Название или ссылка
              <input
                value={placeQuery}
                onChange={(event) => setPlaceQuery(event.target.value)}
                minLength={2}
                maxLength={300}
                placeholder="Например, название места"
              />
            </label>
            <button type="submit" disabled={busy || placeQuery.trim().length < 2}>
              Найти
            </button>
          </form>
        ) : null}
      </div>
    ) : null

  return (
    <section className="dvizh-flow" aria-live="polite">
      <SignalCard dvizh={dvizh} />
      {error ? (
        <p className="inline-notice" role="alert">
          {error}
        </p>
      ) : null}
      {current ? (
        <>
          <h1>Куда пошёл бы?</h1>
          <p className="dvizh-flow__progress">
            {answered + 1} из {actionableCount}
          </p>
          <div
            className="swipe-surface"
            style={{ transform: `translateX(${drag}px) rotate(${drag / 24}deg)` }}
            onPointerDown={(event) => {
              startX.current = event.clientX
              event.currentTarget.setPointerCapture?.(event.pointerId)
            }}
            onPointerMove={(event) => {
              if (startX.current !== null && !busyRef.current) {
                dragX.current = Math.max(-180, Math.min(180, event.clientX - startX.current))
                setDrag(dragX.current)
              }
            }}
            onPointerUp={() => {
              startX.current = null
              const distance = dragX.current
              dragX.current = 0
              if (distance > 90) react(current, 'WOULD_GO')
              else if (distance < -90) react(current, 'PASS')
              else setDrag(0)
            }}
            onPointerCancel={() => {
              startX.current = null
              dragX.current = 0
              setDrag(0)
            }}
          >
            {Math.abs(drag) > 50 ? (
              <span className={`swipe-hint ${drag > 0 ? 'swipe-hint--yes' : ''}`}>
                {drag > 0 ? 'Пошёл бы' : 'Не моё'}
              </span>
            ) : null}
            <ActivityCard candidate={current} />
          </div>
          <div className="swipe-actions">
            <button type="button" disabled={busy} onClick={() => react(current, 'PASS')}>
              Не моё
            </button>
            <button type="button" disabled={busy} onClick={() => react(current, 'WOULD_GO')}>
              Пошёл бы
            </button>
          </div>
          {choosing && dvizh.chosen_count > 0 ? (
            <button
              className="text-action"
              disabled={busy}
              onClick={() => setSelectionFinished(true)}
            >
              Закончить выбор
            </button>
          ) : null}
          {placeSearch}
        </>
      ) : doneChoosing ? (
        <div className="dvizh-result">
          <h1>{dvizh.chosen_count ? `Выбрано: ${dvizh.chosen_count}` : 'Ничего не выбрал'}</h1>
          {dvizh.chosen_count ? (
            <button
              className="primary-button"
              disabled={busy}
              onClick={() => void act(() => api.launch(dvizh.id))}
            >
              Запустить движ
            </button>
          ) : null}
          <div className="inline-actions">
            {(selectionFinished && pending.length > 0) || limit < dvizh.candidates.length ? (
              <button
                className="text-action"
                disabled={busy}
                onClick={() => {
                  setSelectionFinished(false)
                  if (pending.length === 0) setLimit((value) => value + ROUND_SIZE)
                }}
              >
                Показать ещё
              </button>
            ) : null}
            <button className="text-action" onClick={onEdit}>
              Изменить сигнал
            </button>
          </div>
          {placeSearch}
        </div>
      ) : dvizh.status === 'NO_SOURCE' || dvizh.status === 'PROVIDER_UNAVAILABLE' ? (
        <div className="dvizh-result">
          <h1>
            {dvizh.status === 'NO_SOURCE'
              ? 'Пока ничего не нашли'
              : 'Не удалось загрузить варианты'}
          </h1>
          <p>{dvizh.status === 'NO_SOURCE' ? 'Измени время или занятие.' : 'Попробуй ещё раз.'}</p>
          {dvizh.status === 'NO_SOURCE' ? (
            <>
              <button className="primary-button" onClick={onEdit}>
                Изменить
              </button>
              <button
                className="text-action"
                disabled={busy}
                onClick={() =>
                  void act(() => api.moreDvizh(dvizh.id), 'Не удалось загрузить варианты.')
                }
              >
                Повторить поиск
              </button>
            </>
          ) : (
            <>
              <button
                className="primary-button"
                disabled={busy}
                onClick={() =>
                  void act(() => api.moreDvizh(dvizh.id), 'Не удалось загрузить варианты.')
                }
              >
                Повторить
              </button>
              <button className="text-action" onClick={onEdit}>
                Изменить условия
              </button>
            </>
          )}
          {placeSearch}
        </div>
      ) : needsConfirm && match ? (
        <>
          <h1>Похоже, совпало</h1>
          <ActivityCard candidate={match} status={dvizhStatusLabel(dvizh)} />
          <div className="dvizh-result">
            <p>
              {dvizh.confirmed_count} из {dvizh.min_people} подтвердили
            </p>
            {!dvizh.my_confirmation ? (
              <>
                <button
                  className="primary-button"
                  disabled={busy}
                  onClick={() =>
                    match.compatibility === 'NEAR'
                      ? setNearConsent({ candidate: match, action: 'confirm' })
                      : void act(
                          () => api.confirmDvizh(dvizh.id, match.id, false),
                          'Этот вариант уже недоступен.',
                        )
                  }
                >
                  Я в деле
                </button>
                <button
                  className="text-action"
                  disabled={busy}
                  onClick={() => void act(() => api.declineDvizh(dvizh.id))}
                >
                  Не смогу
                </button>
              </>
            ) : waitlisted ? (
              waitlistAction
            ) : (
              <p>{dvizh.my_confirmation === 'CONFIRMED' ? 'Ждём остальных.' : 'Ты отказался.'}</p>
            )}
          </div>
        </>
      ) : dvizh.status === 'GATHERED' && match ? (
        <>
          <h1>⚡ ДВИЖ СОБРАЛСЯ</h1>
          <ActivityCard candidate={match} status="Собрался">
            <p>{dvizh.participants.map((person) => person.display_name).join(' · ')}</p>
          </ActivityCard>
          {waitlistAction}
        </>
      ) : dvizh.status === 'COLLECTING_REACTIONS' || dvizh.status === 'AWAITING_CONFIRMATION' ? (
        <section className="collecting-card" aria-label="Движ собирается">
          <div className="collecting-card__signal" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <h1>Движ собирается</h1>
          <p>Ждём ответы друзей.</p>
          <p>
            {dvizh.chosen_count} {placeNoun} · минимум {formatPeople(dvizh.min_people)}
          </p>
          <button type="button" className="secondary-button" onClick={onNew}>
            Подать ещё сигнал
          </button>
        </section>
      ) : (
        <div className="dvizh-result">
          <h1>Этот движ завершился</h1>
          <button className="primary-button" onClick={onNew}>
            Подать сигнал
          </button>
        </div>
      )}
      {nearConsent ? (
        <ConfirmDialog
          title="Чуть дороже"
          description={`На ${nearConsent.candidate.budget_delta} ₽ выше твоего бюджета.`}
          confirmLabel={nearConsent.action === 'react' ? 'Всё равно пойду' : 'Я в деле'}
          cancelLabel="Отмена"
          busy={busy}
          onCancel={() => setNearConsent(null)}
          onConfirm={() => {
            const { candidate, action } = nearConsent
            setNearConsent(null)
            void act(
              () =>
                action === 'react'
                  ? api.react(dvizh.id, candidate.id, 'WOULD_GO', true)
                  : api.confirmDvizh(dvizh.id, candidate.id, true),
              'Этот вариант уже недоступен.',
            )
          }}
        />
      ) : null}
    </section>
  )
}
