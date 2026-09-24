export type IconName =
  | 'home'
  | 'homeSolid'
  | 'calendar'
  | 'list'
  | 'listSolid'
  | 'users'
  | 'usersSolid'
  | 'chevron'
  | 'more'
  | 'plus'
  | 'minus'
  | 'check'
  | 'pin'
  | 'route'
  | 'money'
  | 'share'
  | 'document'
  | 'ban'
  | 'arrowRight'
  | 'close'
  | 'bell'
  | 'search'

const paths: Record<IconName, React.ReactNode> = {
  search: (
    <>
      <circle cx="10.7" cy="10.7" r="6.7" />
      <path d="m15.6 15.6 5 5" />
    </>
  ),
  home: (
    <>
      <path d="M3.5 10.5 12 3l8.5 7.5" />
      <path d="M5.5 9.5v10h13v-10M9 19.5v-6h6v6" />
    </>
  ),
  homeSolid: (
    <path
      d="M12 2.8 2.5 10.4v9.1a2 2 0 0 0 2 2h5.2v-7h4.6v7h5.2a2 2 0 0 0 2-2v-9.1L12 2.8Z"
      fill="currentColor"
      stroke="none"
    />
  ),
  calendar: (
    <>
      <path d="M5 4.5h14a1.5 1.5 0 0 1 1.5 1.5v13A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V6A1.5 1.5 0 0 1 5 4.5Z" />
      <path d="M7.5 2.5v4M16.5 2.5v4M3.5 9h17" />
    </>
  ),
  list: (
    <>
      <rect x="4" y="2.5" width="16" height="19" rx="3" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </>
  ),
  listSolid: (
    <>
      <rect x="4" y="2.5" width="16" height="19" rx="3" fill="currentColor" stroke="none" />
      <path d="M8 8h8M8 12h8M8 16h5" stroke="white" strokeWidth="1.7" />
    </>
  ),
  users: (
    <>
      <circle cx="8" cy="8" r="3" />
      <path d="M2.5 20v-1a5.5 5.5 0 0 1 11 0v1" />
      <circle cx="17" cy="8.5" r="2.5" />
      <path d="M16 14a5 5 0 0 1 5.5 5v1" />
    </>
  ),
  usersSolid: (
    <>
      <circle cx="8" cy="8" r="3" fill="currentColor" stroke="none" />
      <path d="M2.5 19a5.5 5.5 0 0 1 11 0v1.5h-11V19Z" fill="currentColor" stroke="none" />
      <circle cx="17" cy="8.5" r="2.5" fill="currentColor" stroke="none" />
      <path
        d="M15.5 14.3a5 5 0 0 1 6 4.9v1.3h-6V19a7 7 0 0 0-1.2-4.1Z"
        fill="currentColor"
        stroke="none"
      />
    </>
  ),
  chevron: <path d="m9 5 7 7-7 7" />,
  more: (
    <>
      <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  minus: <path d="M5 12h14" />,
  check: <path d="m5 12 4 4 10-10" />,
  pin: (
    <>
      <path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  route: (
    <>
      <circle cx="5" cy="18" r="2" />
      <circle cx="18" cy="6" r="2" />
      <path d="M7 18h5a4 4 0 0 0 0-8h-1a4 4 0 0 1 0-8h5M18 8v5a5 5 0 0 1-5 5" />
    </>
  ),
  money: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="3" />
      <path d="M2.5 9h19" />
      <circle cx="16.5" cy="14" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  share: (
    <>
      <path d="M10 13.5 18.5 5M13 5h5.5v5.5" />
      <path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4" />
    </>
  ),
  document: (
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </>
  ),
  ban: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m5.5 5.5 13 13" />
    </>
  ),
  arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
  close: <path d="M5 5 19 19M19 5 5 19" />,
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-2.5 7-2.5 9h17C20.5 15 18 15 18 8Z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </>
  ),
}

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}
