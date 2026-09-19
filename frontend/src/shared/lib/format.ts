export const formatDateTime = (value: string) => new Intl.DateTimeFormat('ru-RU', {
  dateStyle: 'medium', timeStyle: 'short',
}).format(new Date(value))

export const formatTime = (value: string) => new Intl.DateTimeFormat('ru-RU', {
  timeStyle: 'short',
}).format(new Date(value))

export const activityLabel = (category: string) => ({
  concert: 'Музыка', exhibition: 'Культура', sport: 'Активности', games: 'Игры', wellness: 'Бани и спа', other: 'Всё равно', any: 'Всё равно',
}[category] ?? 'Досуг')

export const peopleNoun = (count: number) => {
  const lastTwo = Math.abs(count) % 100
  const last = lastTwo % 10
  if (lastTwo >= 11 && lastTwo <= 14) return 'человек'
  if (last === 1) return 'человек'
  if (last >= 2 && last <= 4) return 'человека'
  return 'человек'
}

export const formatPeople = (count: number) => `${count} ${peopleNoun(count)}`

export const formatSignalWindow = (from: string | null, to: string | null) => {
  if (!from || !to) return 'Время не указано'
  const start = new Date(from)
  const now = new Date()
  const tomorrow = new Date(now)
  tomorrow.setDate(now.getDate() + 1)
  const dayKey = (value: Date) => `${value.getFullYear()}-${value.getMonth()}-${value.getDate()}`
  const day = dayKey(start) === dayKey(now) ? 'Сегодня' : dayKey(start) === dayKey(tomorrow) ? 'Завтра' : new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(start)
  return `${day} · ${formatTime(from)}–${formatTime(to)}`
}

export const weekDays = (days: number[] | null) => {
  if (!days?.length) return 'Когда совпадёт'
  const names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  return days.map(day => names[day]).join(' · ')
}
