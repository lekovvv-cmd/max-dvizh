export const activityCatalog = [
  {
    id: 'games',
    label: 'Игры',
    detail: 'Игровые места и развлечения',
    search: 'настольные игры развлечения клуб',
  },
  { id: 'quest', label: 'Квесты', detail: 'Квесты и квест-комнаты', search: 'квест загадки' },
  {
    id: 'anticafe',
    label: 'Антикафе',
    detail: 'Места для встречи и общения',
    search: 'антикафе общение',
  },
  {
    id: 'sport',
    label: 'Активный отдых',
    detail: 'Подвижные занятия и отдых',
    search: 'спорт активность парк',
  },
  {
    id: 'stable',
    label: 'Конные прогулки',
    detail: 'Конюшни и верховая езда',
    search: 'лошади конюшня прогулка',
  },
  {
    id: 'exhibition',
    label: 'Культура',
    detail: 'Выставки, музеи, театр и арт-пространства',
    search: 'искусство арт галерея',
  },
  { id: 'museum', label: 'Музеи', detail: 'Музейные площадки', search: 'музей экспозиция' },
  {
    id: 'theater',
    label: 'Театр',
    detail: 'Спектакли и театральные площадки',
    search: 'театр спектакль',
  },
  {
    id: 'tour',
    label: 'Экскурсии',
    detail: 'Прогулки с программой',
    search: 'экскурсия тур прогулка',
  },
  {
    id: 'concert',
    label: 'Концерты',
    detail: 'Живая музыка и концертные залы',
    search: 'музыка концерт',
  },
  { id: 'party', label: 'Вечеринки', detail: 'Вечеринки и клубы', search: 'танцы дискотека клуб' },
  {
    id: 'wellness',
    label: 'Бани и спа',
    detail: 'Бани, сауны и термы',
    search: 'баня сауна спа spa термы',
  },
] as const

export function activityCategoryLabel(id: string) {
  if (id === 'any' || id === 'other') return 'Любой вариант'
  return activityCatalog.find((item) => item.id === id)?.label ?? 'Досуг'
}

export function searchActivities(query: string) {
  const words = query.trim().toLocaleLowerCase('ru-RU').split(/\s+/).filter(Boolean)
  if (!words.length) return [...activityCatalog]
  return activityCatalog.filter((item) => {
    const haystack = `${item.label} ${item.detail} ${item.search}`.toLocaleLowerCase('ru-RU')
    return words.every((word) => haystack.includes(word))
  })
}
