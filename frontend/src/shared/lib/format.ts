export const formatDateTime = (value: string) => new Intl.DateTimeFormat('ru-RU', {
  dateStyle: 'medium', timeStyle: 'short',
}).format(new Date(value))

export const formatTime = (value: string) => new Intl.DateTimeFormat('ru-RU', {
  timeStyle: 'short',
}).format(new Date(value))

export const activityLabel = (category: string) => ({
  concert: '🎵 Музыка', exhibition: '🎭 Культура', sport: '🏃 Активности', games: '🎮 Игры', wellness: '🧖 Бани и спа', other: 'Всё равно', any: 'Всё равно',
}[category] ?? 'Досуг')

export const weekDays = (days: number[] | null) => {
  if (!days?.length) return 'Когда совпадёт'
  const names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  return days.map(day => names[day]).join(' · ')
}
