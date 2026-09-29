import { useCallback, useState } from 'react'

import { ApiError, MaxAuthError } from '../../app/api'

export type ActionError = { title: string; message: string }
type ActiveActionError = ActionError & { onClose?: () => void }

export function describeActionError(reason: unknown): ActionError {
  if (reason instanceof MaxAuthError) return { title: 'Нужен вход в MAX', message: reason.message }
  if (reason instanceof ApiError) {
    switch (reason.code) {
      case 'SCHEDULE_CONFLICT':
        return {
          title: 'У тебя уже есть планы',
          message: 'На это время у тебя уже есть другой подтверждённый движ. Выбери другое время.',
        }
      case 'CANDIDATE_STALE':
        return {
          title: 'Вариант уже недоступен',
          message: 'Это место больше нельзя выбрать. Покажем актуальные варианты.',
        }
      case 'SELECTION_CLOSED':
        return {
          title: 'Выбор уже завершён',
          message: 'Для этого движа варианты больше не принимаются.',
        }
      case 'NEAR_CONFIRMATION_REQUIRED':
        return { title: 'Подтверди условия', message: 'Этот вариант отличается от твоих условий.' }
      case 'STATE_CONFLICT':
        return {
          title: 'Движ изменился',
          message: 'Открой актуальное состояние и попробуй ещё раз.',
        }
      case 'NOT_FOUND':
        return { title: 'Не найдено', message: 'Запрошенный объект больше недоступен.' }
    }
    if (reason.status === 422)
      return { title: 'Проверь данные', message: 'Проверь заполненные поля и попробуй ещё раз.' }
  }
  return { title: 'Что-то пошло не так', message: 'Попробуй ещё раз.' }
}

export function useActionError() {
  const [error, setError] = useState<ActiveActionError | null>(null)
  const showActionError = useCallback((reason: unknown, onClose?: () => void) => {
    setError({ ...describeActionError(reason), onClose })
  }, [])
  const showActionMessage = useCallback((message: ActionError, onClose?: () => void) => {
    setError({ ...message, onClose })
  }, [])
  const dismissActionError = useCallback(() => {
    setError(null)
    error?.onClose?.()
  }, [error])
  return { actionError: error, showActionError, showActionMessage, dismissActionError }
}
