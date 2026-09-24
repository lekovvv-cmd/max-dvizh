import { Button } from '@maxhub/max-ui'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Company } from '../features/groups/Company'
import { CreateCompany } from '../features/groups/CreateCompany'
import { OfferPool } from '../features/offers/OfferPool'
import { Plans } from '../features/plans/Plans'
import { SignalComposer } from '../features/signals/SignalComposer'
import type { SignalAdjustment } from '../features/signals/SignalComposer'
import { ActiveSignalSummary } from '../features/signals/ActiveSignalSummary'
import { HomeIntro } from '../features/signals/HomeIntro'
import { activityLabel } from '../shared/lib/format'
import { AppShell } from '../shared/ui/AppShell'
import type { Screen } from '../shared/ui/AppShell'
import { ConfirmDialog } from '../shared/ui/ConfirmDialog'
import { api } from './api'
import type { Group, GroupCityUpdateResult, Intent, Location, Offer, Plan } from './api'

function restoreFormNavigation() {
  try {
    const saved = JSON.parse(localStorage.getItem('dvizh-form-navigation') || 'null')
    if (saved?.screen === 'signal')
      return {
        screen: 'signal' as Screen,
        editingBatch: typeof saved.editingBatch === 'string' ? saved.editingBatch : null,
        editingRecurring:
          typeof saved.editingRecurring === 'string' ? saved.editingRecurring : null,
      }
  } catch {
    // A malformed local draft should never block opening the app.
  }
  return { screen: 'home' as Screen, editingBatch: null, editingRecurring: null }
}

function searchStatus(providerState?: string | null) {
  if (providerState === 'NO_SOURCE') return 'Ничего не нашли'
  if (providerState === 'NO_FEASIBLE_PLAN') return 'Нет совпадений'
  if (providerState === 'PROVIDER_UNAVAILABLE') return 'Источник недоступен'
  return 'Ищем варианты'
}

export function App() {
  const restoredNavigation = useRef(restoreFormNavigation())
  const [screen, setScreen] = useState<Screen>(restoredNavigation.current.screen)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshError, setRefreshError] = useState('')
  const loadedOnce = useRef(false)
  const [group, setGroup] = useState<Group | null>(null)
  const [groups, setGroups] = useState<Group[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [locations, setLocations] = useState<Location[]>([])
  const [intents, setIntents] = useState<Intent[]>([])
  const [offers, setOffers] = useState<Offer[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [mode, setMode] = useState('MAX')
  const [chatAvailable, setChatAvailable] = useState(false)
  const [editingBatch, setEditingBatch] = useState<string | null>(
    restoredNavigation.current.editingBatch,
  )
  const [editingRecurring, setEditingRecurring] = useState<string | null>(
    restoredNavigation.current.editingRecurring,
  )
  const [signalAdjustment, setSignalAdjustment] = useState<SignalAdjustment>(null)
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [joinState, setJoinState] = useState('')
  const handledJoinToken = useRef<string | null>(null)
  const [targetId, setTargetId] = useState('')
  const [cancelBatchId, setCancelBatchId] = useState<string | null>(null)
  const [cancelRecurringId, setCancelRecurringId] = useState<string | null>(null)
  const [cancelBusy, setCancelBusy] = useState(false)
  const [resumeBusyId, setResumeBusyId] = useState<string | null>(null)
  useEffect(() => {
    if (screen === 'signal')
      localStorage.setItem(
        'dvizh-form-navigation',
        JSON.stringify({ screen, editingBatch, editingRecurring }),
      )
    else localStorage.removeItem('dvizh-form-navigation')
  }, [screen, editingBatch, editingRecurring])
  const load = useCallback(async () => {
    setError('')
    setRefreshError('')
    try {
      const [session, nextGroups, nextLocations, nextOffers, nextPlans, nextIntents] =
        await Promise.all([
          api.session(),
          api.groups(),
          api.locations(),
          api.offers(),
          api.plans(),
          api.intents(),
        ])
      const selected =
        nextGroups.find((item) => item.id === selectedGroupId) ?? nextGroups[0] ?? null
      setMode(session.max_mode)
      setChatAvailable(Boolean(session.max_chat_id))
      setGroups(nextGroups)
      setGroup(selected)
      setLocations(nextLocations)
      setOffers(nextOffers)
      setPlans(nextPlans)
      setIntents(nextIntents)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'Сервис временно недоступен'
      if (loadedOnce.current) setRefreshError(message)
      else setError(message)
    } finally {
      loadedOnce.current = true
      setLoading(false)
    }
  }, [selectedGroupId])
  useEffect(() => {
    void load()
  }, [load])
  useEffect(() => {
    const token =
      new URLSearchParams(window.location.hash.slice(1)).get('startapp') ||
      new URLSearchParams(window.WebApp?.initData || '').get('start_param')
    if (token?.startsWith('offer_')) {
      setScreen('home')
      setTargetId(`offer-${token.slice(6)}`)
      return
    }
    if (token?.startsWith('plan_')) {
      setScreen('plans')
      setTargetId(`plan-${token.slice(5)}`)
      return
    }
    if (token && handledJoinToken.current !== token) {
      handledJoinToken.current = token
      setJoinState('Вступаем…')
      void api
        .join(token)
        .then((result) => {
          setJoinState(result.already_member ? 'Ты уже участник' : 'Ты в компании')
          setSelectedGroupId(result.group.id)
        })
        .catch((reason) =>
          setJoinState(reason instanceof Error ? reason.message : 'Приглашение недействительно'),
        )
    }
  }, [])
  useEffect(() => {
    if (targetId && !loading)
      document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [targetId, loading, offers, plans])
  if (loading)
    return (
      <main className="system-state" aria-live="polite">
        <span className="loading-indicator" aria-hidden="true" />
        <p>Загружаем…</p>
      </main>
    )
  if (error)
    return (
      <main className="system-state">
        <section className="system-card" role="alert">
          <h1>Не получилось загрузить</h1>
          <p>{error}</p>
          <Button variant="primary" onClick={() => void load()}>
            Повторить
          </Button>
        </section>
      </main>
    )
  if (!group || creatingGroup)
    return (
      <CreateCompany
        chatAvailable={chatAvailable}
        joinState={joinState}
        onCreated={(created) => {
          setSelectedGroupId(created.id)
          setCreatingGroup(false)
        }}
        onCancel={group ? () => setCreatingGroup(false) : undefined}
      />
    )
  const refresh = () => void load()
  const cancelSignal = async () => {
    if (!cancelBatchId && !cancelRecurringId) return
    setCancelBusy(true)
    try {
      if (cancelBatchId) await api.cancelSignalBatch(cancelBatchId)
      if (cancelRecurringId) await api.autoAction(cancelRecurringId, 'cancel')
      setCancelBatchId(null)
      setCancelRecurringId(null)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось отменить сигнал')
    } finally {
      setCancelBusy(false)
    }
  }
  const resumeRecurring = async (id: string) => {
    if (resumeBusyId) return
    setResumeBusyId(id)
    setRefreshError('')
    try {
      await api.autoAction(id, 'resume')
      await load()
    } catch (reason) {
      setRefreshError(reason instanceof Error ? reason.message : 'Не удалось возобновить поиск')
    } finally {
      setResumeBusyId(null)
    }
  }
  const changeGroupCity = async (groupId: string, city: string): Promise<GroupCityUpdateResult> => {
    const result = await api.updateGroupCity(groupId, city)
    const [nextOffers, nextPlans, nextIntents] = await Promise.all([
      api.offers(),
      api.plans(),
      api.intents(),
    ])
    setGroups((current) => current.map((item) => (item.id === groupId ? result.group : item)))
    setGroup(result.group)
    setOffers(nextOffers)
    setPlans(nextPlans)
    setIntents(nextIntents)
    return result
  }
  const addLocation = async (label: string) => {
    if (!navigator.geolocation)
      throw new Error('Геопозиция недоступна. Расстояние останется выключенным.')
    const position = await new Promise<GeolocationPosition>((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 15000,
      }),
    )
    const location = await api.createLocation({
      label,
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      city_slug: group.city_slug,
      kind: 'SAVED',
      is_ephemeral: false,
    })
    setLocations((current) => [location, ...current])
    return location
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
    setLocations((current) => [location, ...current])
    return location
  }
  const activeBatches = (() => {
    const batches = new Map<string, Intent[]>()
    for (const intent of intents)
      if (
        intent.type === 'ONE_TIME' &&
        intent.status === 'ACTIVE' &&
        intent.signal_batch_id &&
        (!intent.expires_at || new Date(intent.expires_at) > new Date())
      )
        batches.set(intent.signal_batch_id, [
          ...(batches.get(intent.signal_batch_id) || []),
          intent,
        ])
    return [...batches.values()]
  })()
  const providerStates = activeBatches.flat().map((intent) => intent.provider_state)
  const recurringIntents = intents.filter(
    (intent) => intent.type === 'RECURRING' && intent.status !== 'CANCELLED',
  )
  const providerState = ['PROVIDER_UNAVAILABLE', 'NO_FEASIBLE_PLAN', 'NO_SOURCE'].find((state) =>
    providerStates.includes(state),
  )
  const collectingPlans = plans.filter((plan) => plan.status === 'COLLECTING')
  const hasActiveSignal =
    activeBatches.length > 0 ||
    collectingPlans.length > 0 ||
    recurringIntents.some((item) => item.status === 'ACTIVE')
  const openNewSignal = () => {
    setEditingBatch(null)
    setEditingRecurring(null)
    setSignalAdjustment(null)
    setScreen('signal')
  }
  const content =
    screen === 'home' ? (
      <div className="page-stack home-page">
        <HomeIntro
          onSignal={openNewSignal}
          onRepeat={() => {
            setEditingBatch(null)
            setEditingRecurring(null)
            setSignalAdjustment('repeat')
            setScreen('signal')
          }}
        />
        {refreshError ? (
          <p className="inline-notice" role="alert">
            {refreshError}{' '}
            <button type="button" className="text-action" onClick={refresh}>
              Повторить
            </button>
          </p>
        ) : null}
        {joinState ? (
          <p className="inline-notice" role="status">
            {joinState}
          </p>
        ) : null}
        {activeBatches.length ? (
          <section className="home-section" aria-label="Активные сигналы">
            {activeBatches.map((batch) => (
              <ActiveSignalSummary
                key={batch[0].signal_batch_id}
                batch={batch}
                groups={groups}
                status={
                  offers.some(
                    (offer) =>
                      offer.status === 'PENDING' &&
                      batch.some((intent) => intent.group_id === offer.group_id),
                  )
                    ? 'Есть приглашение'
                    : collectingPlans.some((plan) =>
                          batch.some((intent) => intent.group_id === plan.group_id),
                        )
                      ? 'Ждём друзей'
                      : searchStatus(
                          batch.find((intent) => intent.provider_state !== 'SEARCHING')
                            ?.provider_state,
                        )
                }
                onEdit={() => {
                  setEditingBatch(batch[0].signal_batch_id)
                  setSignalAdjustment(null)
                  setScreen('signal')
                }}
                onCancel={() => setCancelBatchId(batch[0].signal_batch_id)}
              />
            ))}
          </section>
        ) : null}
        {recurringIntents.length ? (
          <section className="home-section" aria-label="Повторяющиеся сигналы">
            {recurringIntents.map((intent) => (
              <article className="active-signal" key={intent.id}>
                <span className="context-label">
                  {intent.status === 'ACTIVE'
                    ? searchStatus(intent.provider_state)
                    : intent.status === 'PAUSED'
                      ? 'Поиск на паузе'
                      : 'Поиск остановлен'}
                </span>
                <strong className="active-signal__time">
                  Повторяется ·{' '}
                  {intent.weekdays
                    ?.map((day) => ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'][day])
                    .join(', ')}
                </strong>
                <p>
                  {intent.activity_categories.map(activityLabel).join(', ')} ·{' '}
                  {intent.group_name || group.name}
                </p>
                <div className="inline-actions">
                  <button
                    className="text-action"
                    type="button"
                    onClick={() => {
                      setEditingBatch(null)
                      setEditingRecurring(intent.id)
                      setSignalAdjustment(null)
                      setScreen('signal')
                    }}
                  >
                    Изменить
                  </button>
                  {intent.status === 'ACTIVE' ? (
                    <button
                      className="text-action text-action--danger"
                      type="button"
                      onClick={() => setCancelRecurringId(intent.id)}
                    >
                      Остановить
                    </button>
                  ) : intent.status === 'PAUSED' ? (
                    <button
                      className="text-action"
                      type="button"
                      disabled={resumeBusyId === intent.id}
                      onClick={() => void resumeRecurring(intent.id)}
                    >
                      {resumeBusyId === intent.id ? 'Возобновляем…' : 'Возобновить'}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </section>
        ) : null}
        <OfferPool
          offers={offers}
          group={group}
          hasActiveSignal={hasActiveSignal}
          providerState={
            providerState ||
            recurringIntents.find((item) => item.status === 'ACTIVE')?.provider_state
          }
          onRetry={
            activeBatches.length
              ? () => {
                  void Promise.all(
                    activeBatches.map((batch) =>
                      batch[0].signal_batch_id
                        ? api.refreshSignalBatch(batch[0].signal_batch_id)
                        : Promise.resolve(),
                    ),
                  )
                    .then(refresh)
                    .catch((reason) =>
                      setError(
                        reason instanceof Error ? reason.message : 'Не удалось повторить поиск',
                      ),
                    )
                }
              : undefined
          }
          onStop={() => {
            const batchId = activeBatches[0]?.[0]?.signal_batch_id
            if (batchId) setCancelBatchId(batchId)
            else {
              const recurringId = recurringIntents.find((item) => item.status === 'ACTIVE')?.id
              if (recurringId) setCancelRecurringId(recurringId)
            }
          }}
          onEdit={(adjustment) => {
            setEditingBatch(activeBatches[0]?.[0]?.signal_batch_id || null)
            setEditingRecurring(
              activeBatches.length
                ? null
                : recurringIntents.find((item) => item.status === 'ACTIVE')?.id || null,
            )
            setSignalAdjustment(adjustment)
            setScreen('signal')
          }}
          onInvite={() => setScreen('group')}
          currentIntent={
            activeBatches[0]?.[0] || recurringIntents.find((item) => item.status === 'ACTIVE')
          }
          waitingCount={collectingPlans.length}
          onChanged={refresh}
        />
      </div>
    ) : screen === 'signal' ? (
      <SignalComposer
        key={editingBatch || editingRecurring || 'new'}
        group={group}
        groups={groups}
        locations={locations}
        activeBatch={activeBatches.find((batch) => batch[0].signal_batch_id === editingBatch)}
        activeRecurring={recurringIntents.find((item) => item.id === editingRecurring)}
        adjustment={signalAdjustment}
        onCreateLocation={createLocationAt}
        onBack={() => {
          setScreen('home')
          setEditingBatch(null)
          setEditingRecurring(null)
          setSignalAdjustment(null)
        }}
        onDone={async () => {
          await load()
          setScreen('home')
          setEditingBatch(null)
          setEditingRecurring(null)
          setSignalAdjustment(null)
        }}
      />
    ) : screen === 'plans' ? (
      <Plans
        plans={plans}
        onChanged={refresh}
        onSignal={() => {
          setEditingBatch(null)
          setEditingRecurring(null)
          setScreen('signal')
        }}
      />
    ) : (
      <Company
        groups={groups}
        active={group}
        locations={locations}
        mode={mode}
        onChangeCity={changeGroupCity}
        onAddPlace={addLocation}
        onRenamePlace={async (id, label) => {
          const updated = await api.renameLocation(id, label)
          setLocations((current) => current.map((item) => (item.id === id ? updated : item)))
        }}
        onDefaultPlace={async (id) => {
          const updated = await api.defaultLocation(id)
          setLocations((current) =>
            current.map((item) =>
              item.city_slug === updated.city_slug ? { ...item, is_default: item.id === id } : item,
            ),
          )
        }}
        onDeletePlace={async (id) => {
          await api.deleteLocation(id)
          setLocations(await api.locations())
        }}
        onNew={() => setCreatingGroup(true)}
        onSelect={(selected) => {
          if (selected.id === group.id) return
          setGroup(selected)
          setSelectedGroupId(selected.id)
        }}
      />
    )
  return (
    <>
      <AppShell screen={screen} onNavigate={setScreen}>
        {content}
      </AppShell>
      {cancelBatchId || cancelRecurringId ? (
        <ConfirmDialog
          title="Остановить поиск?"
          description="Новые варианты по нему больше не будут собираться."
          confirmLabel="Остановить"
          cancelLabel="Назад"
          busy={cancelBusy}
          onConfirm={() => void cancelSignal()}
          onCancel={() => {
            setCancelBatchId(null)
            setCancelRecurringId(null)
          }}
        />
      ) : null}
    </>
  )
}
