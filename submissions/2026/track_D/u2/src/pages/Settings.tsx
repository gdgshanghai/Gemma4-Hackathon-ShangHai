import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FeatureRow, PageHeader, Sheet } from '../components/AppShell'
import { Button, Notice, SectionLabel } from '../components/UI'
import { Icon } from '../components/Icon'
import { useAppStore } from '../store/appStore'
import { repository } from '../data/repository'
import { createPin, lockSession, unlockPin } from '../services/crypto'
import { localAI } from '../services/localAI'
import { MODEL_SOURCE, WEB_MODEL_ID } from '../config/model'

export default function SettingsPage() {
  const navigate = useNavigate()
  const preferences = useAppStore((state) => state.preferences)!
  const update = useAppStore((state) => state.updatePreferences)
  const setHidden = useAppStore((state) => state.setHidden)
  return <><PageHeader title="设置" subtitle="隐私、模型与本机数据" back /><div className="scroll-area stack"><div className="card stack"><Toggle title="保存聊天记录" text="关闭后原始消息和摘要均不落盘" value={preferences.saveChat} onChange={(value) => void update({ saveChat: value })} /><Toggle title="一键隐藏" text="显示顶部隐藏按钮" value={preferences.hideEnabled} onChange={(value) => void update({ hideEnabled: value })} /></div><FeatureRow icon="lock" title="隐私与 PIN" text={preferences.encrypted ? '敏感记录已使用 PIN 加密' : '当前为本机存储，未加密'} onClick={() => navigate('/settings/privacy')} /><FeatureRow icon="download" title="Gemma 4 本地模型" text="主动下载、状态与缓存管理" onClick={() => navigate('/settings/model')} /><FeatureRow icon="trash" title="数据管理" text="分类删除、全部重置" onClick={() => navigate('/settings/data')} /><FeatureRow icon="eyeoff" title="立即一键隐藏" text="切换到普通备忘录界面" onClick={() => setHidden(true)} /><Notice>U2 不需要账号。未开启 PIN 时，只能表述为“本机存储”，不代表端到端加密。</Notice><div className="app-about"><img src="/icons/u2.svg" alt="" /><strong>U2 v1.0</strong><small>本地优先的 HIV 心理健康与健康支持工具</small></div></div></>
}

function Toggle({ title, text, value, onChange }: { title: string; text: string; value: boolean; onChange: (value: boolean) => void }) {
  return <div className="toggle-row"><div className="grow"><strong>{title}</strong><small>{text}</small></div><button className={`switch ${value ? 'active' : ''}`} onClick={() => onChange(!value)} /></div>
}

export function PrivacyPage() {
  const preferences = useAppStore((state) => state.preferences)!
  const update = useAppStore((state) => state.updatePreferences)
  const showToast = useAppStore((state) => state.showToast)
  const [open, setOpen] = useState(false)
  const [pin, setPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [busy, setBusy] = useState(false)
  async function enable() {
    if (pin !== confirmPin) return showToast('两次 PIN 不一致')
    setBusy(true)
    try {
      const metadata = await createPin(pin)
      await repository.migrateEncryption(true)
      await update({ encrypted: true, pinSalt: metadata.salt, pinVerifier: metadata.verifier })
      setOpen(false)
      showToast('敏感记录已加密')
    } catch (error) {
      showToast(error instanceof Error ? error.message : '无法开启 PIN')
    } finally {
      setBusy(false)
    }
  }
  async function disable() {
    if (!window.confirm('关闭 PIN 后，已有敏感记录将恢复为未加密的本机存储。确认继续吗？')) return
    setBusy(true)
    try {
      await repository.migrateEncryption(false)
      await update({ encrypted: false, pinSalt: undefined, pinVerifier: undefined })
      lockSession()
      showToast('PIN 已关闭')
    } finally {
      setBusy(false)
    }
  }
  return <><PageHeader title="隐私与 PIN" subtitle="密钥仅保留在当前会话" back /><div className="scroll-area stack"><div className={`privacy-status card ${preferences.encrypted ? 'active' : ''}`}><Icon name={preferences.encrypted ? 'lock' : 'shield'} size={30} /><strong>{preferences.encrypted ? 'PIN 加密已开启' : '当前为本机存储'}</strong><p>{preferences.encrypted ? '敏感记录使用 PBKDF2 派生密钥与 AES-GCM 加密。关闭页面后需重新输入 PIN。' : '记录保存在此浏览器的 IndexedDB 中，但尚未使用 PIN 加密。'}</p></div>{preferences.encrypted ? <><Button kind="danger" disabled={busy} onClick={() => void disable()}>关闭 PIN 加密</Button><Notice warm>忘记 PIN 后无法恢复加密数据。U2 不保存 PIN，也没有找回入口。</Notice></> : <Button onClick={() => setOpen(true)}>设置 PIN 并迁移数据</Button>}<SectionLabel>隐私承诺</SectionLabel><div className="card article-text">不强制注册；不收集真实姓名、手机号或住址；默认不主动联网；模型下载和前沿讯息由你主动触发。</div></div>{open && <Sheet title="设置 4–8 位 PIN" onClose={() => setOpen(false)}><div className="stack"><label className="form-label">输入 PIN<input className="field" type="password" inputMode="numeric" maxLength={8} value={pin} onChange={(event) => setPin(event.target.value.replace(/\D/g, ''))} /></label><label className="form-label">再次输入<input className="field" type="password" inputMode="numeric" maxLength={8} value={confirmPin} onChange={(event) => setConfirmPin(event.target.value.replace(/\D/g, ''))} /></label><Notice warm>PIN 无法找回。请使用你能记住、但他人不易猜到的数字。</Notice><Button full disabled={busy || pin.length < 4 || pin !== confirmPin} onClick={() => void enable()}>{busy ? '正在迁移…' : '确认开启'}</Button></div></Sheet>}</>
}

export function UnlockScreen({ onUnlocked }: { onUnlocked: () => void }) {
  const preferences = useAppStore((state) => state.preferences)!
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  async function unlock() {
    try {
      await unlockPin(pin, preferences.pinSalt!, preferences.pinVerifier!)
      onUnlocked()
    } catch {
      setError('PIN 不正确，请重试')
    }
  }
  return <div className="u2-screen unlock-screen"><div className="status-bar"><span>9:41</span><span>•••</span></div><div className="unlock-body"><span className="feature-icon"><Icon name="lock" size={28} /></span><h1>打开 U2</h1><p>输入 PIN 以解锁当前会话中的本地记录。</p><input className="field pin-input" autoFocus type="password" inputMode="numeric" maxLength={8} value={pin} onChange={(event) => { setPin(event.target.value.replace(/\D/g, '')); setError('') }} onKeyDown={(event) => event.key === 'Enter' && void unlock()} placeholder="PIN" />{error && <small className="error-text">{error}</small>}<Button full disabled={pin.length < 4} onClick={() => void unlock()}>解锁</Button><Notice>PIN 和解密密钥不会离开当前设备，也不会写入持久存储。</Notice></div></div>
}

export function ModelPage() {
  const model = useAppStore((state) => state.model)
  const update = useAppStore((state) => state.updatePreferences)
  const showToast = useAppStore((state) => state.showToast)
  const [busy, setBusy] = useState(false)
  async function download() {
    if (!window.confirm('本地 Gemma 4 模型体积较大，将从 Hugging Face 下载并缓存在此浏览器。确认现在开始吗？')) return
    setBusy(true)
    await update({ modelConsent: true })
    const ok = await localAI.initialize()
    setBusy(false)
    showToast(ok ? 'Gemma 4 已在本机就绪' : '模型未能加载，已继续使用安全模板')
  }
  async function clear() {
    if (!window.confirm('确认清除当前浏览器中的模型缓存吗？健康记录不会受影响。')) return
    await localAI.clearCache()
    await update({ modelConsent: false })
    showToast('模型缓存已清理')
  }
  const label = { idle: '尚未下载', checking: '检查 WebGPU', downloading: '正在下载', initializing: '正在初始化', ready: '已就绪', unsupported: '浏览器不支持', error: '加载失败' }[model.status]
  return <><PageHeader title="Gemma 4 本地模型" subtitle={MODEL_SOURCE === 'bundled' ? '随 App 资源读取，不请求模型网络' : '由你主动下载，不自动联网'} back /><div className="scroll-area stack"><div className="model-card card"><div className="row"><span className="feature-icon"><Icon name="spark" /></span><div className="grow"><strong>Gemma 4 E4B · ONNX</strong><small>{MODEL_SOURCE === 'bundled' ? '随包模式 · 本地模型目录' : '桌面 Chrome / Edge + WebGPU'}</small></div><CardStatus status={model.status} label={label} /></div>{['downloading', 'initializing', 'checking'].includes(model.status) && <div className="model-progress"><i style={{ width: `${model.progress}%` }} /></div>}<p>{model.detail || (MODEL_SOURCE === 'bundled' ? '模型将从 /models/ 目录读取。仍需目标 WebView 支持 WebGPU；随包不代表所有手机都能运行。' : `${WEB_MODEL_ID} 会在首次启用时下载到当前浏览器缓存。`)}</p></div>{model.status !== 'ready' && <Button full disabled={busy || ['downloading', 'initializing', 'checking'].includes(model.status)} onClick={() => void download()}><Icon name="download" /> {model.status === 'error' ? '重试加载' : MODEL_SOURCE === 'bundled' ? '加载随包模型' : '下载并启用模型'}</Button>}{model.status === 'ready' && <><Button kind="ghost" full onClick={() => localAI.cancel()}>取消当前任务</Button><Button kind="danger" full onClick={() => void clear()}>清除模型缓存</Button></>}<Notice>{MODEL_SOURCE === 'bundled' ? '随包模型不需要从 Hugging Face 下载，但 Capacitor WebView 的 WebGPU 支持仍需在真机验证。' : '下载模型会产生网络流量。模型失败时，量表、风险分流、记录、提醒和本地知识库仍可使用。'}</Notice></div></>
}

function CardStatus({ status, label }: { status: string; label: string }) {
  return <span className={`model-status ${status}`}>{label}</span>
}

export function DataPage() {
  const showToast = useAppStore((state) => state.showToast)
  const groups = [
    { title: '聊天与摘要', types: ['chat', 'chat-summary', 'trust'] },
    { title: '情绪与测评', types: ['mood', 'assessment', 'risk'] },
    { title: '健康与用药', types: ['health-entry', 'medication-plan', 'medication-log', 'lab-metric', 'timeline'] },
    { title: '病历报告', types: ['report'] },
    { title: '收藏与正念', types: ['favorite', 'mindfulness'] },
  ]
  async function clearGroup(title: string, types: string[]) {
    if (!window.confirm(`确认删除“${title}”中的本机数据吗？此操作无法恢复。`)) return
    for (const type of types) await repository.clearType(type)
    showToast(`${title}已删除`)
  }
  async function reset() {
    if (!window.confirm('确认重置 U2 的全部本机数据和偏好吗？此操作无法恢复。')) return
    if (!window.confirm('请再次确认：全部聊天、健康、病历、设置都将被清空。')) return
    await repository.resetAll()
    window.location.reload()
  }
  return <><PageHeader title="数据管理" subtitle="删除后无法恢复" back /><div className="scroll-area stack"><Notice warm>删除操作只影响当前浏览器。若开启 PIN，忘记 PIN 时也只能重置全部数据。</Notice>{groups.map((group) => <div className="card row" key={group.title}><div className="grow"><strong>{group.title}</strong><small className="block muted">存储在当前设备</small></div><Button small kind="ghost" onClick={() => void clearGroup(group.title, group.types)}>删除</Button></div>)}<Button kind="danger" full onClick={() => void reset()}>重置全部本机数据</Button></div></>
}
