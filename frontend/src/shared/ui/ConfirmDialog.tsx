import { Button } from '@maxhub/max-ui'
import { useEffect, useId, useRef } from 'react'

export function ConfirmDialog({ title, description, confirmLabel, cancelLabel, busy = false, confirmDisabled = false, children, onConfirm, onCancel }: { title: string; description: string; confirmLabel: string; cancelLabel: string; busy?: boolean; confirmDisabled?: boolean; children?: React.ReactNode; onConfirm: () => void; onCancel: () => void }) {
  const titleId = useId()
  const descriptionId = useId()
  const dialogRef = useRef<HTMLElement>(null)
  useEffect(() => {
    dialogRef.current?.focus()
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy) onCancel() }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [busy, onCancel])
  return <div className="dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onCancel() }}>
    <section ref={dialogRef} tabIndex={-1} className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}>
      <h2 id={titleId}>{title}</h2>
      <p id={descriptionId}>{description}</p>
      {children}
      <div className="form-actions">
        <Button variant="primary" loading={busy} disabled={busy || confirmDisabled} onClick={onConfirm}>{confirmLabel}</Button>
        <Button variant="secondary" disabled={busy} onClick={onCancel}>{cancelLabel}</Button>
      </div>
    </section>
  </div>
}
