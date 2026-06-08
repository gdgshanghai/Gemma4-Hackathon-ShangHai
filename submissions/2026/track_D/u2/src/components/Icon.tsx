import type { ReactNode, SVGProps } from 'react'

export type IconName =
  | 'companion' | 'health' | 'support' | 'back' | 'close' | 'eyeoff' | 'history'
  | 'send' | 'plus' | 'mic' | 'lock' | 'shield' | 'chevron' | 'check'
  | 'heart' | 'book' | 'breath' | 'doc' | 'calendar' | 'pill' | 'bed'
  | 'bell' | 'camera' | 'upload' | 'image' | 'file' | 'edit' | 'search'
  | 'star' | 'trash' | 'wifi' | 'leaf' | 'phone' | 'clock' | 'refresh'
  | 'spark' | 'moon' | 'flame' | 'download' | 'settings' | 'chart'

interface Props extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
}

const paths: Record<IconName, ReactNode> = {
  companion: <path d="M21 11.5a8 8 0 0 1-11.5 7.2L4 20l1.4-4.5A8 8 0 1 1 21 11.5Z"/>,
  health: <path d="M3.5 12h4l1.5-4 3 9 2-6 1.5 1h5"/>,
  support: <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.6"/></>,
  back: <path d="M15 5l-7 7 7 7"/>,
  close: <path d="M6 6l12 12M18 6L6 18"/>,
  eyeoff: <><path d="M3 3l18 18M10.6 10.7a2 2 0 0 0 2.8 2.8M9.4 5.3A9.3 9.3 0 0 1 12 5c5 0 8.5 4.2 9.5 6-.5 1-1.7 2.7-3.6 4.1M6.1 6.7C4 8.1 2.8 9.9 2.5 11c.8 1.5 4 6 9.5 6a9.4 9.4 0 0 0 2.5-.3"/></>,
  history: <><path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1M3.5 4.5v3.5H7"/><path d="M12 8v4.2l2.8 1.6"/></>,
  send: <path d="M5 12h13M12 5l7 7-7 7"/>,
  plus: <path d="M12 5v14M5 12h14"/>,
  mic: <><rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v2.5"/></>,
  lock: <><rect x="4.5" y="10.5" width="15" height="10" rx="3"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></>,
  shield: <><path d="M12 3l7 2.5v5.5c0 4.5-3 7.7-7 9.5-4-1.8-7-5-7-9.5V5.5L12 3Z"/><path d="M9 12l2 2 4-4"/></>,
  chevron: <path d="M9 5l7 7-7 7"/>,
  check: <path d="M5 12.5l4.5 4.5L19 7"/>,
  heart: <path d="M12 20s-7-4.6-9.2-9.1C1.4 8 3 4.8 6.2 4.8c2 0 3.2 1.3 4.3 2.8l1.5 1.9 1.5-1.9c1.1-1.5 2.3-2.8 4.3-2.8 3.2 0 4.8 3.2 3.4 6.1C19 15.4 12 20 12 20Z"/>,
  book: <><path d="M5 4.5h9a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H5Z"/><path d="M5 4.5v15"/></>,
  breath: <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4"/></>,
  doc: <><path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"/><path d="M14 3.5V8h4"/></>,
  calendar: <><rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></>,
  pill: <><rect x="3.5" y="9" width="17" height="6" rx="3" transform="rotate(-45 12 12)"/><path d="M9 9l6 6"/></>,
  bed: <path d="M3 18v-7m0 7v-3.5h18V18m0-3.5V11a2 2 0 0 0-2-2h-6.5v5.5M3 11h6"/>,
  bell: <><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z"/><path d="M10 19a2 2 0 0 0 4 0"/></>,
  camera: <><path d="M3.5 8.5h3L8 6h6l1.5 2.5h3A1.5 1.5 0 0 1 20 10v8a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 18v-8A1.5 1.5 0 0 1 4 8.5Z"/><circle cx="12" cy="13.5" r="3.2"/></>,
  upload: <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4.5 15v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/>,
  image: <><rect x="3.5" y="4.5" width="17" height="15" rx="3"/><circle cx="8.5" cy="9.5" r="1.8"/><path d="M4 17l5-4.5 4 3.5 3-2.5 4 4"/></>,
  file: <><path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z"/><path d="M14 3.5V8h4M9 13h6M9 16.5h4"/></>,
  edit: <path d="M14 5.5l4.5 4.5M4 20l1-4L16 5a2.1 2.1 0 0 1 3 3L8 19l-4 1Z"/>,
  search: <><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4 4"/></>,
  star: <path d="M12 3.5l2.4 5.2 5.6.6-4.2 3.8 1.2 5.6L12 16l-5 2.8 1.2-5.6L4 9.3l5.6-.6L12 3.5Z"/>,
  trash: <><path d="M5 7h14M9 7V5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5v2M6.5 7l.8 12a1.5 1.5 0 0 0 1.5 1.4h6.4a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></>,
  wifi: <path d="M2.5 8.5A14 14 0 0 1 21.5 8.5M5.5 12a9.5 9.5 0 0 1 13 0M8.5 15.3a5 5 0 0 1 7 0M12 18.7h.01"/>,
  leaf: <><path d="M5 19c0-8 6-13 14-14 1 8-4 14-12 14"/><path d="M7 17C9 13 12 10 16 8"/></>,
  phone: <path d="M6.5 4h3l1.5 4-2 1.5a11 11 0 0 0 5.5 5.5L16 13l4 1.5v3a2 2 0 0 1-2.2 2A15.5 15.5 0 0 1 4.5 6.2 2 2 0 0 1 6.5 4Z"/>,
  clock: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v4.7l3 2"/></>,
  refresh: <path d="M19 8a7.5 7.5 0 0 0-13-2.2M5 5v3.5h3.5M5 16a7.5 7.5 0 0 0 13 2.2M19 19v-3.5h-3.5"/>,
  spark: <path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6L12 3Z"/>,
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a7 7 0 1 0 10.5 10.5Z"/>,
  flame: <path d="M12 3s4 3.5 4 8a4 4 0 0 1-8 0c0-1.5.6-2.6 1.2-3.4C9.8 8 11 7 12 3Z"/>,
  download: <path d="M12 4v12m0 0l-5-5m5 5 5-5M5 20h14"/>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.7-.7-1.7.9-1.9-2.1-2.1-1.9.9-1.7-.7L10.5 2h-3l-.7 2-1.7.7-1.9-.9-2.1 2.1.9 1.9-.7 1.7-2 .7v3l2 .7.7 1.7-.9 1.9 2.1 2.1 1.9-.9 1.7.7.7 2h3l.7-2 1.7-.7 1.9.9 2.1-2.1-.9-1.9.7-1.7Z" transform="scale(.75) translate(4 4)"/></>,
  chart: <path d="M4 19V9m6 10V5m6 14v-7m4 7H2"/>,
}

export function Icon({ name, size = 20, ...props }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name]}
    </svg>
  )
}
