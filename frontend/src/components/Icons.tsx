import type { ReactNode } from 'react'

function icon(paths: ReactNode) {
  return function Icon({ className = 'size-4' }: { className?: string }) {
    return (
      <svg
        className={className}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {paths}
      </svg>
    )
  }
}

export const EyeIcon = icon(
  <>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </>,
)
export const NetworkIcon = icon(
  <>
    <rect x="9" y="3" width="6" height="5" rx="1" />
    <rect x="3" y="16" width="6" height="5" rx="1" />
    <rect x="15" y="16" width="6" height="5" rx="1" />
    <path d="M12 8v4M6 16v-4h12v4" />
  </>,
)
export const ServerIcon = icon(
  <>
    <rect x="3" y="4" width="18" height="7" rx="2" />
    <rect x="3" y="13" width="18" height="7" rx="2" />
    <path d="M7 7.5h.01M7 16.5h.01" />
  </>,
)
export const LogoutIcon = icon(<path d="M15 4h4v16h-4M10 16l-4-4 4-4M6 12h10" />)
export const RefreshIcon = icon(
  <path d="M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4" />,
)
export const DownloadIcon = icon(<path d="M12 4v11M7 11l5 5 5-5M5 20h14" />)
export const PlusIcon = icon(<path d="M12 5v14M5 12h14" />)
export const TrashIcon = icon(<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />)
export const CloseIcon = icon(<path d="M6 6l12 12M18 6 6 18" />)
export const FitIcon = icon(<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" />)
export const LayoutIcon = icon(
  <>
    <circle cx="6" cy="6" r="2" />
    <circle cx="18" cy="8" r="2" />
    <circle cx="10" cy="18" r="2" />
    <path d="m8 6.3 8 1.4M7 7.8l2 8.3M16.6 9.5l-5.2 7" />
  </>,
)
