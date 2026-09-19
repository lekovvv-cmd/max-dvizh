export function SectionHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return <div className="section-header"><h1>{title}</h1>{action}</div>
}
