export type StatusTone = 'active' | 'confirmed' | 'collecting' | 'conditional' | 'waitlist'

export function StatusLabel({ tone, children }: { tone: StatusTone; children: React.ReactNode }) {
  return (
    <span className={`status-label status-label--${tone}`}>
      <i aria-hidden="true" />
      {children}
    </span>
  )
}
