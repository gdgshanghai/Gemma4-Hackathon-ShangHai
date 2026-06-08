import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from 'react'
import { Icon } from './Icon'

export function StatusBar({ light = false }: { light?: boolean }) {
  return (
    <div className="status-bar" style={light ? { color: 'white' } : undefined}>
      <span>9:41</span>
      <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <span style={{ fontSize: 11 }}>●●●●</span>
        <span style={{ fontSize: 12 }}>⌁</span>
        <span style={{ fontSize: 12 }}>▰</span>
      </span>
    </div>
  )
}

export function Button({
  kind = 'primary',
  small = false,
  full = false,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  kind?: 'primary' | 'ghost' | 'soft' | 'danger'
  small?: boolean
  full?: boolean
}) {
  const kindClass = kind === 'primary' ? '' : kind
  return <button className={`btn ${kindClass} ${small ? 'small' : ''} ${full ? 'full' : ''} ${className}`} {...props} />
}

export function Chip({
  active,
  soft,
  children,
  onClick,
}: PropsWithChildren<{ active?: boolean; soft?: boolean; onClick?: () => void }>) {
  return (
    <button type="button" className={`chip ${active ? 'active' : soft ? 'soft' : ''}`} onClick={onClick}>
      {children}
    </button>
  )
}

export function Notice({ children, warm = false }: PropsWithChildren<{ warm?: boolean }>) {
  return (
    <div className="notice" style={warm ? { background: 'var(--warmSoft)' } : undefined}>
      <Icon name="shield" size={15} style={{ color: warm ? 'var(--warm)' : 'var(--brand)', flex: '0 0 auto', marginTop: 1 }} />
      <span>{children}</span>
    </div>
  )
}

export function SectionLabel({ children }: PropsWithChildren) {
  return <div className="section-label">{children}</div>
}

export function CardTag({ children, warm = false }: PropsWithChildren<{ warm?: boolean }>) {
  return <span className="card-tag" style={warm ? { background: 'var(--warmSoft)', color: 'var(--warm)' } : undefined}>{children}</span>
}

export function EmptyState({
  icon = 'leaf',
  title,
  text,
  action,
}: {
  icon?: Parameters<typeof Icon>[0]['name']
  title: string
  text: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="orb" style={{ width: 58, height: 58, display: 'grid', placeItems: 'center', marginBottom: 16 }}>
        <Icon name={icon} size={25} style={{ color: 'white' }} />
      </div>
      <strong style={{ fontSize: 17 }}>{title}</strong>
      <p style={{ fontSize: 13, lineHeight: 1.6, margin: '8px 0 18px', maxWidth: 270 }}>{text}</p>
      {action}
    </div>
  )
}
