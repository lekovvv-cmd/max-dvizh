export function StatusLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="status-label">
      <i aria-hidden="true" />
      {children}
    </span>
  )
}
