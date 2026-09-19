import { Button } from '@maxhub/max-ui'

export function ConfirmDialog({ title, description, confirmLabel, cancelLabel, busy = false, confirmDisabled = false, children, onConfirm, onCancel }: { title: string; description: string; confirmLabel: string; cancelLabel: string; busy?: boolean; confirmDisabled?: boolean; children?: React.ReactNode; onConfirm: () => void; onCancel: () => void }) {
  return <div className="dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onCancel() }}>
    <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
      <h2 id="confirm-dialog-title">{title}</h2>
      <p>{description}</p>
      {children}
      <div className="form-actions">
        <Button variant="primary" loading={busy} disabled={busy || confirmDisabled} onClick={onConfirm}>{confirmLabel}</Button>
        <Button variant="secondary" disabled={busy} onClick={onCancel}>{cancelLabel}</Button>
      </div>
    </section>
  </div>
}
