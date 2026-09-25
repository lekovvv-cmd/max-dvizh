import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { DvizhFlow } from '../features/dvizhi/DvizhFlow'
import { Company } from '../features/groups/Company'
import { CreateCompany } from '../features/groups/CreateCompany'
import { HomeIntro } from '../features/signals/HomeIntro'
import { SignalComposer } from '../features/signals/SignalComposer'
import { setActivityTaxonomy } from '../shared/lib/activityCatalog'
import { activityLabel, formatSignalWindow } from '../shared/lib/format'
import { currentCoordinates } from '../shared/lib/geolocation'
import { AppShell, type Screen } from '../shared/ui/AppShell'
import { CoachMark, type CoachStep } from '../shared/ui/CoachMark'
import { ConfirmDialog } from '../shared/ui/ConfirmDialog'
import { Icon } from '../shared/ui/Icon'
import {
  api,
  MaxAuthError,
  type Dvizh,
  type Group,
  type GroupCityUpdateResult,
  type Intent,
  type Location,
} from './api'

function initialDeepLink() {
  const hash = new URLSearchParams(window.location.hash.slice(1))
  const token =
    window.WebApp?.initDataUnsafe?.start_param ||
    new URLSearchParams(window.WebApp?.initData || '').get('start_param') ||
    hash.get('WebAppStartParam') ||
    hash.get('startapp') ||
    new URLSearchParams(window.location.search).get('startapp')
  return token || ''
}

function priority(dvizh: Dvizh) {
  if (
    dvizh.status === 'AWAITING_CONFIRMATION' &&
    dvizh.candidates.some(
      (candidate) =>
        candidate.id === dvizh.active_candidate_id && candidate.my_reaction === 'WOULD_GO',
    ) &&
    !dvizh.my_confirmation
  )
    return 0
  if (dvizh.status === 'CHOOSING_CANDIDATES') return 1
  if (
    dvizh.status === 'COLLECTING_REACTIONS' &&
    !dvizh.is_initiator &&
    dvizh.candidates.some((candidate) => !candidate.my_reaction)
  )
    return 2
  if (dvizh.status === 'PROVIDER_UNAVAILABLE' || dvizh.status === 'NO_SOURCE') return 3
  if (dvizh.status === 'COLLECTING_REACTIONS' || dvizh.status === 'AWAITING_CONFIRMATION') return 4
  if (dvizh.status === 'GATHERED') return 5
  return 9
}

function DvizhList({
  items,
  onOpen,
  onSignal,
  recurring,
  onRepeat,
  onPauseRepeat,
  onResumeRepeat,
  onDeleteRepeat,
}: {
  items: Dvizh[]
  onOpen: (id: string) => void
  onSignal: () => void
  recurring?: Intent
  onRepeat: () => void
  onPauseRepeat: () => Promise<void>
  onResumeRepeat: () => Promise<void>
  onDeleteRepeat: () => Promise<void>
}) {
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const collecting = items.filter(
    (item) => !['GATHERED', 'EXPIRED', 'CANCELLED', 'NO_MATCH'].includes(item.status),
  )
  const gathered = items.filter((item) => item.status === 'GATHERED')
  return (
    <section className="page-stack dvizh-list">
      <h1 className="dvizh-list__title">ДВИЖИ</h1>
      {collecting.length ? (
        <section>
          <h2>Собираются</h2>
          {collecting.map((item) => (
            <button className="dvizh-list__item" key={item.id} onClick={() => onOpen(item.id)}>
              <strong>{item.activity_ids.map(activityLabel).join(' или ')}</strong>
              <span>
                {item.group_name} · {formatSignalWindow(item.available_from, item.available_to)}
              </span>
              <small>
                {item.status === 'CHOOSING_CANDIDATES'
                  ? 'Выбери место'
                  : item.status === 'AWAITING_CONFIRMATION'
                    ? 'Нужно подтвердить'
                    : item.status === 'NO_SOURCE' || item.status === 'PROVIDER_UNAVAILABLE'
                      ? 'Нужен новый поиск'
                      : 'Собирается'}
              </small>
            </button>
          ))}
        </section>
      ) : null}
      {gathered.length ? (
        <section>
          <h2>Собрались</h2>
          {gathered.map((item) => (
            <button className="dvizh-list__item" key={item.id} onClick={() => onOpen(item.id)}>
              <strong>
                {item.candidates.find((candidate) => candidate.id === item.active_candidate_id)
                  ?.title || item.activity_ids.map(activityLabel).join(' или ')}
              </strong>
              <span>
                {item.group_name} · {formatSignalWindow(item.available_from, item.available_to)}
              </span>
              <small>Собрался · {item.participants.length} участников</small>
            </button>
          ))}
        </section>
      ) : null}
      {recurring ? (
        <section className="dvizh-result">
          <h2>Регулярный сигнал</h2>
          {recurring.status === 'PAUSED' ? <p>На паузе</p> : null}
          <p>
            {recurring.group_name} ·{' '}
            {recurring.weekdays
              ?.map((day) => ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][day])
              .join(', ')}{' '}
            · {recurring.local_start}–{recurring.local_end}
          </p>
          <div className="inline-actions">
            <button className="text-action" onClick={onRepeat}>
              Изменить
            </button>
            <button
              className="text-action"
              onClick={() =>
                void (recurring.status === 'PAUSED' ? onResumeRepeat() : onPauseRepeat())
              }
            >
              {recurring.status === 'PAUSED' ? 'Возобновить' : 'Приостановить'}
            </button>
            <button className="text-action" onClick={() => setDeleteOpen(true)}>
              Удалить
            </button>
          </div>
        </section>
      ) : null}
      {deleteOpen ? (
        <ConfirmDialog
          title="Удалить автосигнал?"
          description="Новые движи по этому расписанию создаваться не будут. Данные сигнала сохранятся в истории."
          confirmLabel="Удалить автосигнал"
          cancelLabel="Оставить"
          busy={deleteBusy}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => {
            setDeleteBusy(true)
            void onDeleteRepeat()
              .then(
                () => setDeleteOpen(false),
                () => undefined,
              )
              .finally(() => setDeleteBusy(false))
          }}
        />
      ) : null}
      {!collecting.length && !gathered.length ? (
        <div className="dvizh-result">
          <h2>Пока нет движей</h2>
          <p>Подай сигнал, выбери место, и мы спросим компанию.</p>
          <button className="primary-button" onClick={onSignal}>
            Подать сигнал
          </button>
        </div>
      ) : null}
    </section>
  )
}

export function App() {
  const [screen, setScreen] = useState<Screen>(() =>
    initialDeepLink().startsWith('dvizh_') ? 'dvizhi' : 'home',
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [authRequired, setAuthRequired] = useState(false)
  const [groups, setGroups] = useState<Group[]>([])
  const [groupId, setGroupId] = useState<string | null>(null)
  const [locations, setLocations] = useState<Location[]>([])
  const [intents, setIntents] = useState<Intent[]>([])
  const [dvizhi, setDvizhi] = useState<Dvizh[]>([])
  const [mode, setMode] = useState('MAX')
  const [chatAvailable, setChatAvailable] = useState(false)
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [joinError, setJoinError] = useState('')
  const [targetId, setTargetId] = useState<string | null>(() => {
    const token = initialDeepLink()
    return token.startsWith('dvizh_') ? token.slice(6) : null
  })
  const [detailReturn, setDetailReturn] = useState<'home' | 'dvizhi'>('dvizhi')
  const [editingBatch, setEditingBatch] = useState<string | null>(null)
  const [repeat, setRepeat] = useState(false)
  const [introStep, setIntroStep] = useState(0)
  const [introDone, setIntroDone] = useState(true)
  const introInitialized = useRef(false)

  const load = useCallback(async () => {
    setError('')
    setAuthRequired(false)
    try {
      const [session, nextGroups, nextLocations, nextIntents, nextDvizhi, taxonomy] =
        await Promise.all([
          api.session(),
          api.groups(),
          api.locations(),
          api.intents(),
          api.dvizhi(),
          api.taxonomy(),
        ])
      setActivityTaxonomy(taxonomy)
      setMode(session.max_mode)
      setChatAvailable(Boolean(session.max_chat_id))
      if (!introInitialized.current) {
        introInitialized.current = true
        setIntroDone(session.onboarding_seen)
        if (!session.onboarding_seen) void api.markOnboardingSeen().catch(() => undefined)
      }
      setGroups(nextGroups)
      setLocations(nextLocations)
      setIntents(nextIntents)
      setDvizhi(nextDvizhi)
    } catch (reason) {
      setAuthRequired(reason instanceof MaxAuthError)
      setError(reason instanceof Error ? reason.message : 'Не получилось загрузить данные')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])
  useEffect(() => {
    if (!loading && targetId && !dvizhi.some((item) => item.id === targetId)) {
      void api
        .dvizh(targetId)
        .then((item) =>
          setDvizhi((current) =>
            current.some((value) => value.id === item.id) ? current : [item, ...current],
          ),
        )
        .catch(() => setTargetId(null))
    }
  }, [loading, targetId, dvizhi])
  useEffect(() => {
    const token = initialDeepLink()
    if (!token || token.startsWith('dvizh_')) return
    void api
      .join(token)
      .then((result) => {
        setGroupId(result.group.id)
        void load()
      })
      .catch((reason) =>
        setJoinError(reason instanceof Error ? reason.message : 'Приглашение недействительно'),
      )
  }, [load])
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (
        dvizhi.some((item) =>
          ['COLLECTING_REACTIONS', 'AWAITING_CONFIRMATION'].includes(item.status),
        )
      ) {
        void api
          .dvizhi()
          .then(setDvizhi)
          .catch(() => undefined)
      }
    }, 15000)
    return () => window.clearInterval(timer)
  }, [dvizhi])

  const group = groups.find((item) => item.id === groupId) || groups[0] || null
  const recurring = intents.find(
    (item) =>
      item.type === 'RECURRING' &&
      ['ACTIVE', 'PAUSED'].includes(item.status) &&
      item.group_id === group?.id,
  )
  const focused = dvizhi.find((item) => item.id === targetId)
  const homeDvizhi = useMemo(() => {
    return dvizhi
      .filter(
        (item) =>
          item.group_id === group?.id &&
          !['CANCELLED', 'EXPIRED', 'NO_MATCH'].includes(item.status),
      )
      .sort((a, b) => priority(a) - priority(b))
  }, [dvizhi, group?.id])
  const coachStep: CoachStep | null =
    screen === 'home' && !introDone
      ? (['signal', 'choice', 'dvizhi'] as CoachStep[])[introStep]
      : null
  const finishCoach = () => {
    if (introStep < 2) setIntroStep((value) => value + 1)
    else skipCoach()
  }
  const skipCoach = () => {
    void api.markOnboardingSeen().catch(() => undefined)
    setIntroDone(true)
  }
  const updateDvizh = (value: Dvizh) =>
    setDvizhi((items) => items.map((item) => (item.id === value.id ? value : item)))
  const openSignal = (batch: string | null = null, recurring = false) => {
    setEditingBatch(batch)
    setRepeat(recurring)
    setScreen('signal')
  }
  const editDvizh = (item: Dvizh) => openSignal(item.signal_batch_id)

  if (loading)
    return (
      <main className="system-state" aria-live="polite">
        <span className="loading-indicator" aria-hidden="true" />
        <p>Загружаем…</p>
      </main>
    )
  if (error && !groups.length)
    return (
      <main className="system-state">
        <section className="system-card" role="alert">
          <h1>{authRequired ? 'Открой ДВИЖ в MAX' : 'Не получилось загрузить'}</h1>
          <p>{error}</p>
          {authRequired ? (
            <a className="primary-button" href="https://max.ru/t57_hakaton_max_bot?startapp">
              Открыть через MAX
            </a>
          ) : (
            <button className="primary-button" onClick={() => void load()}>
              Повторить
            </button>
          )}
        </section>
      </main>
    )
  if (!group || creatingGroup)
    return (
      <CreateCompany
        chatAvailable={chatAvailable}
        onCreated={(created) => {
          setGroupId(created.id)
          setCreatingGroup(false)
          void load()
        }}
        onCancel={group ? () => setCreatingGroup(false) : undefined}
      />
    )

  const changeGroupCity = async (id: string, city: string): Promise<GroupCityUpdateResult> => {
    const result = await api.updateGroupCity(id, city)
    setGroups((items) => items.map((item) => (item.id === id ? result.group : item)))
    await load()
    return result
  }
  const createLocationAt = async (
    label: string,
    latitude: number,
    longitude: number,
    city: string,
    kind: 'SAVED' | 'CURRENT' = 'SAVED',
  ) => {
    const location = await api.createLocation({
      label,
      latitude,
      longitude,
      city_slug: city,
      kind,
      is_ephemeral: false,
    })
    setLocations((items) => [location, ...items])
    return location
  }
  const addLocation = async (label: string, latitude?: number, longitude?: number) => {
    const coordinates =
      latitude === undefined || longitude === undefined
        ? await currentCoordinates()
        : { latitude, longitude }
    return createLocationAt(label, coordinates.latitude, coordinates.longitude, group.city_slug)
  }
  const batch = intents.filter(
    (item) => item.signal_batch_id === editingBatch && item.status === 'ACTIVE',
  )
  const content =
    screen === 'signal' ? (
      <SignalComposer
        key={editingBatch || String(repeat)}
        group={group}
        groups={groups}
        locations={locations}
        activeBatch={batch.length ? batch : undefined}
        activeRecurring={repeat ? recurring : undefined}
        adjustment={repeat ? 'repeat' : null}
        onCreateLocation={createLocationAt}
        onBack={() => setScreen('home')}
        onDone={async (created) => {
          await load()
          const next = created?.find((item) => item.group_id === group.id) ?? created?.[0]
          if (next) {
            setDvizhi((items) => [next, ...items.filter((item) => item.id !== next.id)])
            setGroupId(next.group_id)
            setDetailReturn('home')
            setTargetId(next.id)
            setScreen('dvizhi')
          } else {
            setTargetId(null)
            setScreen('home')
          }
        }}
      />
    ) : screen === 'group' ? (
      <Company
        groups={groups}
        active={group}
        locations={locations}
        mode={mode}
        onChangeCity={changeGroupCity}
        onAddPlace={addLocation}
        onRenamePlace={async (id, label) => {
          const value = await api.renameLocation(id, label)
          setLocations((items) => items.map((item) => (item.id === id ? value : item)))
        }}
        onDefaultPlace={async (id) => {
          const value = await api.defaultLocation(id)
          setLocations((items) =>
            items.map((item) =>
              item.city_slug === value.city_slug ? { ...item, is_default: item.id === id } : item,
            ),
          )
        }}
        onDeletePlace={async (id) => {
          await api.deleteLocation(id)
          setLocations(await api.locations())
        }}
        onNew={() => setCreatingGroup(true)}
        onSelect={(value) => {
          setGroupId(value.id)
          setTargetId(null)
        }}
      />
    ) : screen === 'dvizhi' && !focused ? (
      <DvizhList
        items={dvizhi}
        onOpen={(id) => {
          setDetailReturn('dvizhi')
          setTargetId(id)
        }}
        onSignal={() => openSignal()}
        recurring={recurring}
        onRepeat={() => openSignal(null, true)}
        onPauseRepeat={async () => {
          if (!recurring) return
          try {
            await api.pauseRecurringSignal(recurring.id)
            await load()
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Не удалось приостановить сигнал')
            throw reason
          }
        }}
        onResumeRepeat={async () => {
          if (!recurring) return
          try {
            await api.resumeRecurringSignal(recurring.id)
            await load()
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Не удалось возобновить сигнал')
            throw reason
          }
        }}
        onDeleteRepeat={async () => {
          if (!recurring) return
          try {
            await api.deleteRecurringSignal(recurring.id)
            await load()
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Не удалось удалить сигнал')
            throw reason
          }
        }}
      />
    ) : screen === 'dvizhi' && focused ? (
      <div className="page-stack home-page">
        <button
          type="button"
          className="dvizh-back"
          aria-label={
            detailReturn === 'home' ? 'Вернуться на главную' : 'Вернуться к списку движей'
          }
          onClick={() => {
            setTargetId(null)
            setScreen(detailReturn)
          }}
        >
          <Icon name={detailReturn === 'home' ? 'home' : 'list'} size={18} />
          Назад
        </button>
        <DvizhFlow
          key={focused.id}
          dvizh={focused}
          onUpdate={updateDvizh}
          onEdit={() => editDvizh(focused)}
          onNew={() => openSignal()}
        />
      </div>
    ) : (
      <div className="page-stack home-page">
        <HomeIntro
          onSignal={() => openSignal()}
          onRepeat={() => openSignal(null, true)}
          hasRepeat={Boolean(recurring && recurring.status === 'ACTIVE')}
        />
        {homeDvizhi.length ? (
          <section className="home-dvizhi" aria-labelledby="home-dvizhi-title">
            <h2 id="home-dvizhi-title">Твои движи</h2>
            <div className="home-dvizhi__list">
              {homeDvizhi.map((item) => (
                <button
                  type="button"
                  className="home-dvizhi__item"
                  key={item.id}
                  onClick={() => {
                    setDetailReturn('home')
                    setTargetId(item.id)
                    setScreen('dvizhi')
                  }}
                >
                  <strong>{item.activity_ids.map(activityLabel).join(' или ')}</strong>
                  <span>{formatSignalWindow(item.available_from, item.available_to)}</span>
                  <small>
                    {item.status === 'CHOOSING_CANDIDATES'
                      ? 'Выбери место'
                      : item.status === 'AWAITING_CONFIRMATION'
                        ? 'Нужно подтвердить'
                        : item.status === 'NO_SOURCE' || item.status === 'PROVIDER_UNAVAILABLE'
                          ? 'Нужен новый поиск'
                          : item.status === 'GATHERED'
                            ? 'Собрались'
                            : 'Собирается'}
                  </small>
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    )

  return (
    <>
      <AppShell
        screen={screen}
        onNavigate={(value) => {
          setTargetId(null)
          setScreen(value)
        }}
      >
        {error ? (
          <p className="inline-notice" role="alert">
            {error}
          </p>
        ) : null}
        {content}
      </AppShell>
      {coachStep ? <CoachMark step={coachStep} onDone={finishCoach} onSkip={skipCoach} /> : null}
      {joinError ? (
        <ConfirmDialog
          title="Не удалось открыть приглашение"
          description={joinError}
          confirmLabel="Понятно"
          onConfirm={() => setJoinError('')}
          onCancel={() => setJoinError('')}
        />
      ) : null}
    </>
  )
}
