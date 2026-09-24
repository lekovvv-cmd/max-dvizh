export type Group = {
  id: string
  name: string
  city_slug: string
  member_count: number
  max_chat_bound: boolean
  invite_token?: string | null
  invite_url?: string | null
}
export type Taxonomy = {
  directions: { id: string; label: string }[]
  activities: { id: string; label: string; directions: string[] }[]
}
export type DvizhCandidate = {
  id: string
  title: string
  venue_name: string | null
  starts_at: string
  ends_at: string
  price_text: string | null
  price_min: number | null
  distance_km: number | null
  address_text: string | null
  source_url: string | null
  image_url: string | null
  activity_ids: string[]
  compatibility: string
  budget_delta: number | null
  expires_at: string
  my_reaction: 'WOULD_GO' | 'PASS' | null
  position: number
}
export type Dvizh = {
  id: string
  signal_batch_id: string | null
  group_id: string
  group_name: string
  status: string
  is_initiator: boolean
  activity_ids: string[]
  min_people: number
  max_people: number
  available_from: string | null
  available_to: string | null
  expires_at: string
  active_candidate_id: string | null
  candidates: DvizhCandidate[]
  chosen_count: number
  reaction_count: number
  confirmed_count: number
  my_confirmation: string | null
  participants: { id: string; display_name: string }[]
}
export type GroupMember = { id: string; display_name: string; is_me: boolean }
export type GroupCityUpdateResult = {
  group: Group
  cancelled_signals: number
  paused_autosignals: number
  cancelled_plans: number
  invalidated_offers: number
}
export type Location = {
  id: string
  label: string
  city_slug: string
  kind: string
  address_text: string | null
  is_default: boolean
}
export type Intent = {
  id: string
  type: string
  status: string
  provider_state: string
  name: string | null
  city_slug: string
  group_id: string
  group_name: string | null
  signal_batch_id: string | null
  activity_category: string
  activity_categories: string[]
  available_from: string | null
  available_to: string | null
  budget_max: number | null
  radius_km: number | null
  origin_location_id: string | null
  min_people: number
  max_people: number | null
  expires_at: string | null
  weekdays: number[] | null
  local_start: string | null
  local_end: string | null
}
declare global {
  interface Window {
    WebApp?: {
      initData?: string
      shareMaxContent?: (params: { text?: string; link?: string }) => void
      openMaxLink?: (url: string) => void
    }
  }
}

let demoUser = localStorage.getItem('dvizh-demo-user') || 'anton'
export function setDemoUser(value: string) {
  demoUser = value
  localStorage.setItem('dvizh-demo-user', value)
}

export class ApiTimeoutError extends Error {
  constructor() {
    super('Связь пропала. Проверяем, сохранился ли сигнал.')
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (window.WebApp?.initData) headers.set('X-MAX-Init-Data', window.WebApp.initData)
  else headers.set('X-Demo-User', demoUser)
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 25000)
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      ...init,
      headers,
      signal: init.signal ?? controller.signal,
    })
  } catch (reason) {
    if (controller.signal.aborted) throw new ApiTimeoutError()
    throw new Error('Нет связи. Проверь интернет и попробуй ещё раз.', { cause: reason })
  } finally {
    window.clearTimeout(timeout)
  }
  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Keep a useful local fallback when the server did not send JSON.
    }
    if (detail && /[А-Яа-яЁё]/.test(detail)) throw new Error(detail)
    if (response.status === 422) throw new Error('Проверь заполненные поля и попробуй ещё раз.')
    if (response.status === 404) throw new Error('Этот вариант больше недоступен. Обнови страницу.')
    throw new Error('Сервис временно недоступен. Попробуй ещё раз.')
  }
  try {
    return (await response.json()) as T
  } catch {
    throw new Error('Сервис временно недоступен. Попробуйте ещё раз.')
  }
}

export const api = {
  session: () =>
    request<{ id: string; display_name: string; max_mode: string; max_chat_id: string | null }>(
      '/session',
    ),
  groups: () => request<Group[]>('/groups'),
  groupMembers: (id: string) => request<GroupMember[]>(`/groups/${id}/members`),
  createGroup: (body: { name: string; city_slug: string; bind_current_chat?: boolean }) =>
    request<Group>('/groups', { method: 'POST', body: JSON.stringify(body) }),
  updateGroupCity: (id: string, city_slug: string) =>
    request<GroupCityUpdateResult>(`/groups/${id}/city`, {
      method: 'PUT',
      body: JSON.stringify({ city_slug }),
    }),
  join: (token: string) =>
    request<{ group: Group; already_member: boolean }>(`/groups/join/${token}`, { method: 'POST' }),
  locations: () => request<Location[]>('/locations'),
  createLocation: (body: object) =>
    request<Location>('/locations', { method: 'POST', body: JSON.stringify(body) }),
  renameLocation: (id: string, label: string) =>
    request<Location>(`/locations/${id}`, { method: 'PATCH', body: JSON.stringify({ label }) }),
  defaultLocation: (id: string) =>
    request<Location>(`/locations/${id}/default`, { method: 'POST' }),
  deleteLocation: (id: string) =>
    request<{ status: string }>(`/locations/${id}`, { method: 'DELETE' }),
  intents: () => request<Intent[]>('/intents'),
  signalBatch: (body: object, requestId?: string) =>
    request<{ signal_batch_id: string; dvizhi: Dvizh[] }>('/signals', {
      method: 'POST',
      body: JSON.stringify(body),
      headers: requestId ? { 'X-Request-ID': requestId } : undefined,
    }),
  editSignalBatch: (id: string, body: object, requestId?: string) =>
    request<{ signal_batch_id: string; dvizhi: Dvizh[] }>(`/signals/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
      headers: requestId ? { 'X-Request-ID': requestId } : undefined,
    }),
  cancelSignalBatch: (id: string) =>
    request<{ status: string }>(`/signals/${id}`, { method: 'DELETE' }),
  recurringSignal: (body: object) =>
    request<{ id: string; status: string }>('/recurring-signals', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  editRecurringSignal: (id: string, body: object) =>
    request<{ id: string; status: string }>(`/recurring-signals/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  cancelRecurringSignal: (id: string) =>
    request<{ id: string; status: string }>(`/recurring-signals/${id}`, { method: 'DELETE' }),
  cities: () => request<{ slug: string; name: string }[]>('/leisure/cities'),
  taxonomy: () => request<Taxonomy>('/leisure/taxonomy'),
  dvizhi: () => request<Dvizh[]>('/dvizhi'),
  dvizh: (id: string) => request<Dvizh>(`/dvizhi/${id}`),
  react: (id: string, candidate: string, value: 'WOULD_GO' | 'PASS', near = false) =>
    request<Dvizh>(`/dvizhi/${id}/candidates/${candidate}/reaction`, {
      method: 'PUT',
      body: JSON.stringify({ value, confirm_near_exception: near }),
    }),
  launch: (id: string) => request<Dvizh>(`/dvizhi/${id}/launch`, { method: 'POST' }),
  confirmDvizh: (id: string, candidateId: string, near = false) =>
    request<Dvizh>(`/dvizhi/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ candidate_id: candidateId, confirm_near_exception: near }),
    }),
  declineDvizh: (id: string) => request<Dvizh>(`/dvizhi/${id}/decline`, { method: 'POST' }),
  moreDvizh: (id: string) => request<Dvizh>(`/dvizhi/${id}/more`, { method: 'POST' }),
  searchPlace: (id: string, query: string) =>
    request<Dvizh>(`/dvizhi/${id}/places/search`, {
      method: 'POST',
      body: JSON.stringify({ query }),
    }),
}
