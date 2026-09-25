import type { Dvizh } from '../../app/api'

export function needsDvizhConfirmation(item: Dvizh): boolean {
  return (
    item.status === 'AWAITING_CONFIRMATION' &&
    !item.my_confirmation &&
    item.candidates.some(
      (candidate) =>
        candidate.id === item.active_candidate_id && candidate.my_reaction === 'WOULD_GO',
    )
  )
}

export function dvizhStatusLabel(item: Dvizh): string {
  if (item.status === 'CHOOSING_CANDIDATES') return 'Выбери место'
  if (item.status === 'NO_SOURCE' || item.status === 'PROVIDER_UNAVAILABLE')
    return 'Нужен новый поиск'
  if (item.my_confirmation === 'WAITLISTED') return 'Ты в листе ожидания'
  if (item.my_confirmation === 'CONFIRMED') return 'Ты в деле'
  if (item.my_confirmation === 'DECLINED') return 'Ты отказался'
  if (needsDvizhConfirmation(item)) return 'Нужно подтвердить'
  if (item.status === 'GATHERED') return 'Собрались'
  return 'Собирается'
}
