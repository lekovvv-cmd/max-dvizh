import { useEffect, useRef } from 'react'

const steps = [
  { title: 'Подай сигнал', detail: 'Когда и куда хочешь.' },
  { title: 'Выбери места', detail: 'Куда реально пошёл бы.' },
  { title: 'ДВИЖ спросит друзей', detail: 'Если совпадёт — подтвердите участие.' },
]

export function CoachMark({
  onDone,
  busy,
  error,
}: {
  onDone: () => void
  busy: boolean
  error: string
}) {
  const dialog = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialog.current?.focus()
    return () => previousFocus?.focus()
  }, [])

  return (
    <>
      <div className="coach-backdrop" aria-hidden="true" />
      <div
        className="coach"
        role="dialog"
        aria-modal="true"
        aria-labelledby="coach-title"
        tabIndex={-1}
        ref={dialog}
        onKeyDown={(event) => {
          if (event.key === 'Tab') {
            event.preventDefault()
            dialog.current?.querySelector('button')?.focus()
          }
        }}
      >
        <h2 id="coach-title">Как работает ДВИЖ</h2>
        <ol className="coach__steps">
          {steps.map((step, index) => (
            <li key={step.title}>
              <span aria-hidden="true">{index + 1}</span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="button" className="primary-button" disabled={busy} onClick={onDone}>
          Понятно
        </button>
      </div>
    </>
  )
}
