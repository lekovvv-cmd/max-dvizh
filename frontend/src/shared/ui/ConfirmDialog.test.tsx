import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

afterEach(cleanup)

describe('ConfirmDialog keyboard access', () => {
  it('keeps Tab inside the dialog and restores the opener on close', () => {
    const onCancel = vi.fn()
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    const { unmount } = render(
      <ConfirmDialog
        title="Удалить?"
        description="Проверка"
        confirmLabel="Удалить"
        cancelLabel="Оставить"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )
    const dialog = screen.getByRole('dialog')
    const close = screen.getByRole('button', { name: 'Закрыть' })
    const cancel = screen.getByRole('button', { name: 'Оставить' })
    expect(dialog).toHaveFocus()
    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(close).toHaveFocus()
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true })
    expect(cancel).toHaveFocus()
    fireEvent.keyDown(cancel, { key: 'Tab' })
    expect(close).toHaveFocus()
    fireEvent.click(close)
    expect(onCancel).toHaveBeenCalledOnce()
    opener.focus()
    expect(dialog).toHaveFocus()
    unmount()
    expect(opener).toHaveFocus()
    opener.remove()
  })

  it('does not dismiss during a request or steal focus on rerender', () => {
    const onCancel = vi.fn()
    const props = {
      title: 'Сохранить?',
      description: 'Проверка',
      confirmLabel: 'Да',
      cancelLabel: 'Нет',
      onConfirm: vi.fn(),
      onCancel,
    }
    const { rerender } = render(
      <ConfirmDialog {...props}>
        <input aria-label="Название" />
      </ConfirmDialog>,
    )
    screen.getByRole('textbox').focus()
    rerender(
      <ConfirmDialog {...props} busy>
        <input aria-label="Название" />
      </ConfirmDialog>,
    )
    expect(screen.getByRole('textbox')).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onCancel).not.toHaveBeenCalled()
    rerender(
      <ConfirmDialog {...props}>
        <input aria-label="Название" />
      </ConfirmDialog>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledOnce()
  })
})
