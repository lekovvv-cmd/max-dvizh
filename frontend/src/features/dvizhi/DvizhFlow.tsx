import { useRef, useState } from 'react'

import { api, type Dvizh, type DvizhCandidate } from '../../app/api'
import { activityLabel } from '../../shared/lib/format'
import { ActivityCard } from '../../shared/ui/ActivityCard'
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
    (candidate) => !candidate.my_reaction && new Date(candidate.expires_at) > new Date(),
  )
  const current = dvizh.status === 'AWAITING_CONFIRMATION' ? undefined : pending[0]
  const answered = stack.length - pending.length
  const match = dvizh.candidates.find((candidate) => candidate.id === dvizh.active_candidate_id)

  async function act(action: () => Promise<Dvizh>) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError('')
    try {
      onUpdate(await action())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось сохранить. Попробуй ещё раз.')
    } finally {
      busyRef.current = false
      setBusy(false)
      setDrag(0)
      dragX.current = 0
    }
  }

  function react(candidate: DvizhCandidate, value: 'WOULD_GO' | 'PASS') {
    const near = value === 'WOULD_GO' && candidate.compatibility === 'NEAR'
    if (
      near &&
      !window.confirm(`Бюджет выше на ${candidate.budget_delta} ₽. Всё равно пошёл бы?`)
    ) {
      setDrag(0)
      dragX.current = 0
      return
    }
    void act(() => api.react(dvizh.id, candidate.id, value, near))
  }

  const summary = dvizh.activity_ids.map(activityLabel).join(' или ')
  const doneChoosing = choosing && !current && limit >= dvizh.candidates.length
  const needsConfirm = dvizh.status === 'AWAITING_CONFIRMATION' && match?.my_reaction === 'WOULD_GO'
  const waitlisted = dvizh.my_confirmation === 'WAITLISTED'
  const waitlistAction =
    waitlisted && match ? (
      <div className="dvizh-result">
        <p>Ты в листе ожидания. Проверь позже, освободилось ли место.</p>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() =>
            void act(() => api.confirmDvizh(dvizh.id, match.id, match.compatibility === 'NEAR'))
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
          Знаешь место? Найти по названию или ссылке
        </button>
        {placeOpen ? (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (placeQuery.trim().length >= 2)
                void act(() => api.searchPlace(dvizh.id, placeQuery.trim()))
            }}
          >
            <label>
              Название или ссылка KudaGo
              <input
                value={placeQuery}
                onChange={(event) => setPlaceQuery(event.target.value)}
                minLength={2}
                maxLength={300}
                placeholder="Название или ссылка на место в KudaGo"
              />
            </label>
            <button type="submit" disabled={busy || placeQuery.trim().length < 2}>
              Найти
            </button>
            <p>Покажем место, только если KudaGo подтверждает занятие и время.</p>
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
          <p className="dvizh-flow__lead">
            {choosing
              ? 'Отметь места, куда ты реально готов пойти.'
              : 'Твои ответы приватны. Выбирай только то, что тебе подходит.'}
          </p>
          <p className="dvizh-flow__progress">
            {answered + 1} из {stack.length}
          </p>
          <div
            className="swipe-surface"
            data-coach="choice"
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
              ← Не моё
            </button>
            <button type="button" disabled={busy} onClick={() => react(current, 'WOULD_GO')}>
              Пошёл бы →
            </button>
          </div>
          <p className="dvizh-flow__hint">Свайп влево или вправо тоже работает</p>
          {choosing && dvizh.chosen_count > 0 ? (
            <button
              className="text-action"
              disabled={busy}
              onClick={() => void act(() => api.launch(dvizh.id))}
            >
              Завершить выбор и запустить движ
            </button>
          ) : null}
          {placeSearch}
        </>
      ) : doneChoosing ? (
        <div className="dvizh-result">
          <h1>{dvizh.chosen_count ? `Выбрано: ${dvizh.chosen_count}` : 'Ничего не зацепило'}</h1>
          <p>
            {dvizh.chosen_count
              ? `${summary}. Ты отметил места, куда готов пойти.`
              : 'В каталоге ДВИЖа пока не нашли подходящего тебе места.'}
          </p>
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
            {limit < dvizh.candidates.length ? (
              <button
                className="text-action"
                disabled={busy}
                onClick={() => setLimit((value) => value + ROUND_SIZE)}
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
      ) : choosing && limit < dvizh.candidates.length ? (
        <div className="dvizh-result">
          <h1>Выбор сохранён</h1>
          <button
            className="primary-button"
            onClick={() => setLimit((value) => value + ROUND_SIZE)}
          >
            Показать ещё
          </button>
          {dvizh.chosen_count ? (
            <button
              className="text-action"
              disabled={busy}
              onClick={() => void act(() => api.launch(dvizh.id))}
            >
              Запустить движ
            </button>
          ) : null}
        </div>
      ) : dvizh.status === 'NO_SOURCE' || dvizh.status === 'PROVIDER_UNAVAILABLE' ? (
        <div className="dvizh-result">
          <h1>
            {dvizh.status === 'NO_SOURCE' ? 'Пока не нашли места' : 'Источник временно недоступен'}
          </h1>
          <p>
            {dvizh.status === 'NO_SOURCE'
              ? 'KudaGo не дал проверенных мест для выбранного занятия и времени. Можно изменить условия или найти конкретное место по названию либо ссылке на KudaGo.'
              : 'Не смогли получить места из KudaGo. Попробуй повторить поиск чуть позже.'}
          </p>
          <button className="primary-button" onClick={onEdit}>
            Изменить занятие или время
          </button>
          <button
            className="text-action"
            disabled={busy}
            onClick={() => void act(() => api.moreDvizh(dvizh.id))}
          >
            Повторить поиск
          </button>
          {placeSearch}
        </div>
      ) : needsConfirm && match ? (
        <>
          <h1>Похоже, совпало</h1>
          <ActivityCard candidate={match} status="Нужно подтвердить" />
          <div className="dvizh-result">
            <p>
              {dvizh.confirmed_count} из {dvizh.min_people} подтвердили участие
            </p>
            {!dvizh.my_confirmation ? (
              <>
                <button
                  className="primary-button"
                  disabled={busy}
                  onClick={() => {
                    const near = match.compatibility === 'NEAR'
                    if (
                      !near ||
                      window.confirm(
                        `Бюджет выше на ${match.budget_delta} ₽. Подтверждаешь участие?`,
                      )
                    )
                      void act(() => api.confirmDvizh(dvizh.id, match.id, near))
                  }}
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
              <p>Ответ сохранён. Ждём остальных.</p>
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
        <div className="dvizh-result">
          <h1>Движ собирается</h1>
          <p>
            {summary}. Остальных спросит ДВИЖ. Можно закрыть приложение — мы напишем в MAX, когда
            понадобится твой ответ.
          </p>
        </div>
      ) : (
        <div className="dvizh-result">
          <h1>Этот движ завершился</h1>
          <p>Подай новый сигнал, если хочешь собрать компанию.</p>
          <button className="primary-button" onClick={onNew}>
            Подать сигнал
          </button>
        </div>
      )}
    </section>
  )
}
