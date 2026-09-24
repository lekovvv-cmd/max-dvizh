import { useEffect, useRef } from 'react'

export type CoachStep = 'signal' | 'choice' | 'dvizhi'
const copy: Record<CoachStep, { title: string; body: string; number: number }> = {
  signal: {
    title: 'Подай сигнал',
    body: 'Скажи, когда и куда ты готов пойти. Остальных спросит ДВИЖ.',
    number: 1,
  },
  choice: {
    title: 'Выбери, куда пошёл бы',
    body: 'Свайпни вправо или нажми кнопку. Твои ответы приватны.',
    number: 2,
  },
  dvizhi: {
    title: 'Дальше ДВИЖ сам',
    body: 'Мы спросим друзей и напишем в MAX, когда понадобится твой ответ.',
    number: 3,
  },
}

export function CoachMark({
  step,
  onDone,
  onSkip,
}: {
  step: CoachStep
  onDone: () => void
  onSkip: () => void
}) {
  const dialog = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const target = document.querySelector<HTMLElement>(`[data-coach="${step}"]`)
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialog.current?.focus()
    if (!target) return () => previousFocus?.focus()
    const previous = {
      position: target.style.position,
      zIndex: target.style.zIndex,
      boxShadow: target.style.boxShadow,
      borderRadius: target.style.borderRadius,
    }
    target.style.position = 'relative'
    target.style.zIndex = '1001'
    target.style.boxShadow = '0 0 0 9999px rgb(13 0 26 / 65%)'
    target.style.borderRadius = '16px'
    return () => {
      Object.assign(target.style, previous)
      previousFocus?.focus()
    }
  }, [step])
  return (
    <div
      className="coach"
      role="dialog"
      aria-modal="true"
      aria-label={copy[step].title}
      tabIndex={-1}
      ref={dialog}
      onKeyDown={(event) => {
        if (event.key === 'Escape') onSkip()
        if (event.key === 'Tab') {
          const buttons = dialog.current?.querySelectorAll('button')
          if (!buttons?.length) return
          const first = buttons[0]
          const last = buttons[buttons.length - 1]
          if (
            event.shiftKey &&
            (document.activeElement === first || document.activeElement === dialog.current)
          ) {
            event.preventDefault()
            last.focus()
          } else if (
            !event.shiftKey &&
            (document.activeElement === last || document.activeElement === dialog.current)
          ) {
            event.preventDefault()
            first.focus()
          }
        }
      }}
    >
      <span>{copy[step].number} / 3</span>
      <h2>{copy[step].title}</h2>
      <p>{copy[step].body}</p>
      <div className="coach__actions">
        <button type="button" onClick={onSkip}>
          Пропустить
        </button>
        <button type="button" onClick={onDone}>
          {step === 'dvizhi' ? 'Понятно' : 'Далее'}
        </button>
      </div>
    </div>
  )
}
