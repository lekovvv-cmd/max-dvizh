import { useEffect, useId, useRef, useState } from 'react'
import { Icon } from '../../shared/ui/Icon'

const EXIT_DURATION_MS = 190

export function CompanyPopup({
  open,
  title,
  description,
  busy = false,
  className = '',
  onClose,
  children,
}: {
  open: boolean
  title: string
  description?: string
  busy?: boolean
  className?: string
  onClose: () => void
  children: React.ReactNode
}) {
  const [rendered, setRendered] = useState(open)
  const titleId = useId()
  const descriptionId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  const busyRef = useRef(busy)

  useEffect(() => {
    closeRef.current = onClose
    busyRef.current = busy
  }, [onClose, busy])

  useEffect(() => {
    if (open) {
      setRendered(true)
      return
    }
    if (!rendered) return
    const duration = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      ? 0
      : EXIT_DURATION_MS
    const timeout = window.setTimeout(() => setRendered(false), duration)
    return () => window.clearTimeout(timeout)
  }, [open, rendered])

  useEffect(() => {
    if (!open || !rendered) return
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current
    dialog?.focus()
    const handleKey = (event: KeyboardEvent) => {
      if (!dialog) return
      if (event.key === 'Escape' && !busyRef.current) {
        event.preventDefault()
        closeRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const controls = [
        ...dialog.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]',
        ),
      ]
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (!first) {
        event.preventDefault()
        dialog.focus()
      } else if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === dialog)
      ) {
        event.preventDefault()
        last.focus()
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || document.activeElement === dialog)
      ) {
        event.preventDefault()
        first.focus()
      }
    }
    const keepFocusInside = (event: FocusEvent) => {
      if (event.target instanceof Node && !dialog?.contains(event.target)) dialog?.focus()
    }
    document.addEventListener('keydown', handleKey)
    document.addEventListener('focusin', keepFocusInside)
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.removeEventListener('focusin', keepFocusInside)
      if (opener?.isConnected) opener.focus()
    }
  }, [open, rendered])

  if (!rendered) return null

  return (
    <div
      className="company-place-overlay"
      data-state={open ? 'open' : 'closing'}
      data-open={open}
      aria-hidden={open ? undefined : true}
      inert={!open}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className={`company-place-dialog${className ? ` ${className}` : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <button
          type="button"
          className="company-place-dialog__close"
          aria-label="Закрыть"
          disabled={busy}
          onClick={onClose}
        >
          <Icon name="close" size={18} />
        </button>
        <div className="company-place-dialog__body">
          <h2 id={titleId}>{title}</h2>
          {description ? (
            <p className="company-place-dialog__description" id={descriptionId}>
              {description}
            </p>
          ) : null}
          {children}
        </div>
      </div>
    </div>
  )
}
