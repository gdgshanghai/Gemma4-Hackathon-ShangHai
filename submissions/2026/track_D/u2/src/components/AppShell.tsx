import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Icon, type IconName } from './Icon'
import { StatusBar } from './UI'
import { useAppStore } from '../store/appStore'

const tabs: Array<{ path: string; label: string; icon: IconName }> = [
  { path: '/companion', label: '陪伴', icon: 'companion' },
  { path: '/health', label: '健康', icon: 'health' },
  { path: '/support', label: '支持', icon: 'support' },
]

const MODEL_BANNER_STATUSES = new Set(['checking', 'downloading', 'initializing'])

export function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const preferences = useAppStore((state) => state.preferences)
  const toast = useAppStore((state) => state.toast)
  const model = useAppStore((state) => state.model)
  const showBanner = MODEL_BANNER_STATUSES.has(model.status)

  const bannerLabel = model.status === 'checking'
    ? '正在检测 AI 运行环境…'
    : model.status === 'initializing'
      ? `正在初始化${model.detail ? ` · ${model.detail}` : ' AI 模型'}…`
      : `正在下载${model.detail ? ` · ${model.detail}` : ' AI 模型'} · ${model.progress}%`

  return (
    <div className="u2-screen">
      <StatusBar />
      {showBanner && (
        <button className="model-banner" onClick={() => navigate('/settings/model')}>
          <div className="model-banner-row">
            <span className="model-banner-label">{bannerLabel}</span>
            <Icon name="chevron" size={14} className="model-banner-chevron" />
          </div>
          <div className="model-banner-track">
            <div className="model-banner-fill" style={{ width: `${model.progress}%` }} />
          </div>
        </button>
      )}
      <div className="route-stage"><Outlet /></div>
      <nav className="bottom-tabs" aria-label="主要功能">
        {tabs.map((tab) => {
          const active = location.pathname.startsWith(tab.path)
          return (
            <button key={tab.path} className={`tab-button ${active ? 'active' : ''}`} onClick={() => navigate(tab.path)}>
              <Icon name={tab.icon} size={22} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </nav>
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  back = false,
  settings = false,
  action,
}: {
  title: string
  subtitle?: string
  back?: boolean
  settings?: boolean
  action?: React.ReactNode
}) {
  const navigate = useNavigate()
  const preferences = useAppStore((state) => state.preferences)
  const setHidden = useAppStore((state) => state.setHidden)
  return (
    <header className="topbar">
      {back && <button className="icon-button" onClick={() => navigate(-1)}><Icon name="back" /></button>}
      <div className="grow">
        <div className="wordmark">{title}</div>
        {subtitle && <div className="page-subtitle">{subtitle}</div>}
      </div>
      {action}
      {settings && <button className="icon-button" onClick={() => navigate('/settings')}><Icon name="settings" /></button>}
      {preferences?.hideEnabled && (
        <button className="icon-button privacy-peek" onClick={() => setHidden(true)} title="一键隐藏">
          <Icon name="eyeoff" size={16} />
        </button>
      )}
    </header>
  )
}

export function FeatureRow({
  icon,
  title,
  text,
  onClick,
  right,
  warm = false,
}: {
  icon: IconName
  title: string
  text?: string
  onClick?: () => void
  right?: React.ReactNode
  warm?: boolean
}) {
  return (
    <button type="button" className="feature-row" onClick={onClick}>
      <span className="feature-icon" style={warm ? { background: 'var(--warmSoft)', color: 'var(--warm)' } : undefined}>
        <Icon name={icon} size={20} />
      </span>
      <span className="grow" style={{ textAlign: 'left' }}>
        <strong>{title}</strong>
        {text && <small>{text}</small>}
      </span>
      {right ?? <Icon name="chevron" size={17} className="muted" />}
    </button>
  )
}

export function Sheet({ title, onClose, children }: React.PropsWithChildren<{ title: string; onClose: () => void }>) {
  return (
    <div className="sheet-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="sheet">
        <div className="sheet-grab" />
        <div className="topbar">
          <div className="wordmark grow">{title}</div>
          <button className="icon-button" onClick={onClose}><Icon name="close" /></button>
        </div>
        <div className="scroll-area">{children}</div>
      </div>
    </div>
  )
}
