export type Group = {
  id: string
  name: string
  city_slug: string
  member_count: number
  max_chat_bound: boolean
  invite_token?: string | null
  invite_url?: string | null
}
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
export type Offer = {
  id: string
  status: string
  is_near: boolean
  group_id: string
  group_name: string
  title: string
  venue_name: string | null
  starts_at: string
  ends_at: string
  price_text: string | null
  price_min: number | null
  price_kind: string
  address_text: string | null
  opening_hours_unverified: boolean
  is_demo: boolean
  source_url: string | null
  source_fetched_at: string
  distance_km: number | null
  required_min_people: number
  required_max_people: number
  accepted_count: number
  conditional_count: number
  effective_max: number
  remaining_to_confirm: number
  remaining_capacity: number
  waitlist_count: number
  can_waitlist: boolean
  can_accept: boolean
  expires_at: string
  budget_delta: number | null
}
export type Plan = {
  id: string
  status: string
  title: string
  venue_name: string | null
  starts_at: string
  ends_at: string
  price_text: string | null
  price_kind: string
  address_text: string | null
  opening_hours_unverified: boolean
  source_url: string | null
  participant_count: number
  conditional_count: number
  personal_response_count: number | null
  personal_required_min: number | null
  required_min_people: number
  required_max_people: number
  group_id: string
  group_name: string
  remaining_to_confirm: number
  remaining_capacity: number
  participants: { id: string; display_name: string }[]
  my_offer_id: string | null
  my_status: string | null
  share_text: string
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (window.WebApp?.initData) headers.set('X-MAX-Init-Data', window.WebApp.initData)
  else headers.set('X-Demo-User', demoUser)
  const response = await fetch(`/api/v1${path}`, { ...init, headers })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    if (typeof detail === 'string' && detail.trim()) throw new Error(detail)
    if (response.status === 422) throw new Error('Проверь заполненные поля и попробуй ещё раз.')
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
  signalBatch: (body: object) =>
    request<{ signal_batch_id: string; intents: Intent[] }>('/signal-batches', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  editSignalBatch: (id: string, body: object) =>
    request<{ signal_batch_id: string; intents: Intent[] }>(`/signal-batches/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  refreshSignalBatch: (id: string) =>
    request<{ signal_batch_id: string; intents: Intent[] }>(`/signal-batches/${id}/refresh`, {
      method: 'POST',
    }),
  cancelSignalBatch: (id: string) =>
    request<{ status: string }>(`/signal-batches/${id}`, { method: 'DELETE' }),
  autosignal: (body: object) =>
    request<Intent>('/autosignals', { method: 'POST', body: JSON.stringify(body) }),
  editAutosignal: (id: string, body: object) =>
    request<Intent>(`/autosignals/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  autoAction: (id: string, action: string) =>
    request<Intent>(`/autosignals/${id}/${action}`, { method: 'POST' }),
  offers: () => request<Offer[]>('/offers'),
  accept: (id: string, near: boolean) =>
    request<Offer>(`/offers/${id}/accept`, {
      method: 'POST',
      body: JSON.stringify({ confirm_near_exception: near }),
    }),
  reject: (id: string) => request<Offer>(`/offers/${id}/reject`, { method: 'POST' }),
  cancelAcceptance: (id: string) => request<Offer>(`/offers/${id}/cancel`, { method: 'POST' }),
  plans: () => request<Plan[]>('/plans'),
  cities: () => request<{ slug: string; name: string }[]>('/leisure/cities'),
}
