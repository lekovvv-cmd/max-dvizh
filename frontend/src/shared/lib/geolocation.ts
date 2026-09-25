export type Coordinates = { latitude: number; longitude: number }

export function parseCoordinates(latitude: string, longitude: string): Coordinates | null {
  if (!latitude.trim() || !longitude.trim()) return null
  const lat = Number(latitude.trim().replace(',', '.'))
  const lon = Number(longitude.trim().replace(',', '.'))
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180)
    return null
  return { latitude: lat, longitude: lon }
}

export function geolocationError(reason: unknown): string {
  if (reason && typeof reason === 'object' && 'code' in reason) {
    if (reason.code === 1)
      return 'Доступ к геопозиции запрещён. Разреши его для MAX или браузера либо введи координаты из карты.'
    if (reason.code === 3)
      return 'Не дождались геопозиции. Попробуй ещё раз или введи координаты из карты.'
  }
  return 'Не получилось определить геопозицию. Введи координаты из карты.'
}

export function currentCoordinates(): Promise<Coordinates> {
  if (!navigator.geolocation) return Promise.reject(new Error('Geolocation unavailable'))
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({ latitude: position.coords.latitude, longitude: position.coords.longitude }),
      reject,
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 },
    )
  })
}
