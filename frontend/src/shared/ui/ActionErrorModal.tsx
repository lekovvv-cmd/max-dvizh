import { createPortal } from 'react-dom'

import type { ActionError } from './actionErrors'
import { ConfirmDialog } from './ConfirmDialog'

export function ActionErrorModal({
  error,
  onClose,
}: {
  error: ActionError | null
  onClose: () => void
}) {
  return error
    ? createPortal(
        <div data-action-error-modal>
          <ConfirmDialog
            title={error.title}
            description={error.message}
            confirmLabel="Понятно"
            onConfirm={onClose}
            onCancel={onClose}
          />
        </div>,
        document.body,
      )
    : null
}
