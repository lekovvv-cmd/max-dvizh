export function DvizhProgress({ current, target, label }: { current: number; target: number; label: string }) {
  const count = Math.max(2, Math.min(12, target))
  return <div className="dvizh-progress" aria-label={label}>
    <span className="dvizh-progress__dots" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => <i key={index} className={index < current ? 'is-filled' : ''} />)}
    </span>
    <span>{label}</span>
  </div>
}
