export type IconName = 'home' | 'repeat' | 'calendar' | 'users' | 'bolt' | 'chevron' | 'more' | 'plus' | 'check'

const paths: Record<IconName, React.ReactNode> = {
  home: <><path d="M3.5 10.5 12 3l8.5 7.5" /><path d="M5.5 9.5v10h13v-10M9 19.5v-6h6v6" /></>,
  repeat: <><path d="M20 7h-9a6 6 0 0 0-5.65 4" /><path d="m17 4 3 3-3 3" /><path d="M4 17h9a6 6 0 0 0 5.65-4" /><path d="m7 20-3-3 3-3" /></>,
  calendar: <><path d="M5 4.5h14a1.5 1.5 0 0 1 1.5 1.5v13A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V6A1.5 1.5 0 0 1 5 4.5Z" /><path d="M7.5 2.5v4M16.5 2.5v4M3.5 9h17" /><path d="m8.5 14 2 2 5-5" /></>,
  users: <><path d="M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M16 5.2a3.3 3.3 0 0 1 0 6.4M17 14a5.5 5.5 0 0 1 4.5 5.4" /></>,
  bolt: <path d="m13.5 2.5-8 11h6l-1 8 8-11h-6l1-8Z" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  more: <><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  check: <path d="m5 12 4 4 10-10" />,
}

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
