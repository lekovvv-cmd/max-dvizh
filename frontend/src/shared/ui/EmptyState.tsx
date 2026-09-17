import { Button } from '@maxhub/max-ui'

export function EmptyState({ title, children, action }: { title: string; children: React.ReactNode; action?: { label: string; onClick: () => void } }) {
  return <section className="empty-state">
    <span className="empty-state__spark" aria-hidden="true">⚡</span>
    <h2>{title}</h2>
    <p>{children}</p>
    {action ? <Button variant="primary" stretched onClick={action.onClick}>{action.label}</Button> : null}
  </section>
}
