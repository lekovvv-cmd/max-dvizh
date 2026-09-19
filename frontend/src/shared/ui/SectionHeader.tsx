export function SectionHeader({
  title,
  action,
  id,
}: {
  title: string
  action?: React.ReactNode
  id?: string
}) {
  return (
    <div className="section-header">
      <h1 id={id}>{title}</h1>
      {action}
    </div>
  )
}
