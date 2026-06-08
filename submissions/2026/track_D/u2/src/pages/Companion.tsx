import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ChatMessage, MoodLabel, TrustEvidence } from '../types'
import { PageHeader, Sheet } from '../components/AppShell'
import { Button, CardTag, Chip, EmptyState, Notice, SectionLabel } from '../components/UI'
import { Icon } from '../components/Icon'
import { useAppStore } from '../store/appStore'
import { useChatStore } from '../store/chatStore'
import { repository } from '../data/repository'
import { currentTrustLevel, inferTrustEvidence } from '../services/trust'
import { hasCrisisSignal, runAgent } from '../services/agent'
import { uid } from '../utils'

const greeting: ChatMessage = {
  id: 'session-greeting',
  conversationId: 'local',
  role: 'assistant',
  content: '你好，我是 U2。你不用组织好语言，也不用先证明自己的担心是否“合理”。今天想从哪里说起？',
  createdAt: Date.now(),
}

export default function CompanionPage() {
  const navigate = useNavigate()
  const preferences = useAppStore((state) => state.preferences)!
  const model = useAppStore((state) => state.model)
  const showToast = useAppStore((state) => state.showToast)
  const conversationId = useChatStore((state) => state.conversationId)
  const messages = useChatStore((state) => state.messages)
  const setMessages = useChatStore((state) => state.setMessages)
  const addMessage = useChatStore((state) => state.addMessage)
  const updateMessage = useChatStore((state) => state.updateMessage)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [moodOpen, setMoodOpen] = useState(false)
  const [crisis, setCrisis] = useState(false)
  const [evidence, setEvidence] = useState<TrustEvidence[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    void (async () => {
      const loadedEvidence = await repository.list<TrustEvidence>('trust', 1, 20)
      setEvidence(loadedEvidence.items.reverse())
      if (!messages.length && preferences.saveChat) {
        const saved = await repository.list<ChatMessage>('chat', 1, 40)
        setMessages(saved.items.reverse())
      }
    })()
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  const visibleMessages = messages.length ? messages : [greeting]
  const trust = useMemo(() => currentTrustLevel(evidence), [evidence])

  async function persist(message: ChatMessage) {
    if (preferences.saveLocal && preferences.saveChat) await repository.save('chat', message)
  }

  async function send(text = input.trim()) {
    if (!text || sending) return
    setInput('')
    const user: ChatMessage = { id: uid('msg'), conversationId, role: 'user', content: text, createdAt: Date.now() }
    addMessage(user)
    await persist(user)
    const foundEvidence = inferTrustEvidence(text)
    if (foundEvidence) {
      setEvidence((items) => [...items, foundEvidence])
      if (preferences.saveLocal) await repository.save('trust', foundEvidence)
    }
    if (hasCrisisSignal(text)) setCrisis(true)
    setSending(true)
    const assistant: ChatMessage = { id: uid('msg'), conversationId, role: 'assistant', content: '', createdAt: Date.now() }
    addMessage(assistant)
    let streamed = ''
    const reply = await runAgent(text, messages, foundEvidence ? currentTrustLevel([...evidence, foundEvidence]) : trust, evidence, (chunk) => {
      streamed += chunk
      updateMessage(assistant.id, streamed)
    })
    updateMessage(assistant.id, reply.content)
    await persist({ ...assistant, content: reply.content })
    if (preferences.saveLocal && preferences.saveChat) {
      await repository.save('chat-summary', {
        id: `summary-${conversationId}`,
        conversationId,
        title: text.slice(0, 18),
        summary: reply.content.slice(0, 90),
        createdAt: Date.now(),
      })
    }
    setSending(false)
    if (reply.crisis) setCrisis(true)
  }

  return (
    <>
      <PageHeader title="U2 陪伴" subtitle="本地优先 · 不评判" settings action={
        <button className="icon-button" onClick={() => navigate('/companion/history')}><Icon name="history" /></button>
      } />
      <div className="companion-intro">
        <div><span className="orb" /><strong>我在这里</strong></div>
        <small>{model.status === 'ready' ? 'Gemma 4 已在本机就绪' : '当前使用安全模板，核心功能仍可用'}</small>
      </div>
      <div className="quick-strip">
        <Chip soft onClick={() => send('我想了解 U=U')}>U=U 知识</Chip>
        <Chip soft onClick={() => navigate('/health/risk')}>HIV 风险评估</Chip>
        <Chip soft onClick={() => navigate('/health/assessments')}>心理测评</Chip>
        <Chip soft onClick={() => setMoodOpen(true)}>记录情绪</Chip>
      </div>
      <div ref={scrollRef} className="scroll-area chat-scroll">
        <div className="daily-task card">
          <div className="row"><CardTag>今日小任务</CardTag><span className="grow" /><small className="muted">约 2 分钟</small></div>
          <strong>把最担心的一件事写成一句话</strong>
          <p>不必解决它，只是把它从脑海里放到这里。</p>
        </div>
        <div className="chat-list">
          {visibleMessages.map((message) => (
            <div key={message.id} className={message.role === 'user' ? 'user-bubble' : 'ai-bubble'}>
              {message.content || <span className="typing-dots">正在整理…</span>}
            </div>
          ))}
        </div>
        {!preferences.saveChat && <Notice>当前聊天不会保存。离开后，原始消息和摘要都不会写入本机数据库。</Notice>}
      </div>
      <div className="input-bar">
        <button className="icon-button" onClick={() => setMoodOpen(true)}><Icon name="plus" /></button>
        <textarea className="chat-input" rows={1} value={input} onChange={(event) => setInput(event.target.value)} placeholder="和 U2 说点什么…" onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() }
        }} />
        <button className="icon-button send-button" disabled={!input.trim() || sending} onClick={() => void send()}><Icon name="send" /></button>
      </div>
      {moodOpen && <MoodSheet onClose={() => setMoodOpen(false)} onDone={() => { setMoodOpen(false); showToast('情绪已记录到健康时间线') }} />}
      {crisis && <CrisisSheet onClose={() => setCrisis(false)} />}
    </>
  )
}

function MoodSheet({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [label, setLabel] = useState<MoodLabel>('焦虑')
  const [intensity, setIntensity] = useState(6)
  const [note, setNote] = useState('')
  const options: MoodLabel[] = ['害怕', '焦虑', '难过', '平静', '麻木', '愤怒', '想哭', '想找人聊聊']
  async function save() {
    const record = { id: uid('mood'), label, intensity, note, createdAt: Date.now() }
    await repository.save('mood', record)
    await repository.save('timeline', { id: uid('timeline'), category: '情绪', title: `情绪：${label}`, summary: `${intensity}/10${note ? ` · ${note}` : ''}`, createdAt: Date.now(), refId: record.id })
    onDone()
  }
  return (
    <Sheet title="记录此刻的情绪" onClose={onClose}>
      <div className="stack">
        <div className="chip-grid">{options.map((item) => <Chip key={item} active={label === item} onClick={() => setLabel(item)}>{item}</Chip>)}</div>
        <label className="form-label">强度 <strong>{intensity}/10</strong><input type="range" min="1" max="10" value={intensity} onChange={(event) => setIntensity(Number(event.target.value))} /></label>
        <textarea className="field" value={note} onChange={(event) => setNote(event.target.value)} placeholder="发生了什么？可以留空" />
        <Button full onClick={() => void save()}>保存情绪</Button>
      </div>
    </Sheet>
  )
}

function CrisisSheet({ onClose }: { onClose: () => void }) {
  return (
    <div className="sheet-backdrop crisis-backdrop">
      <div className="sheet crisis-sheet">
        <div className="sheet-grab" />
        <div className="scroll-area stack">
          <span className="crisis-heart"><Icon name="heart" size={28} /></span>
          <h2>先确保你此刻的安全</h2>
          <p>请尽量去到有人的地方，把可能伤害自己的工具放远，并联系一个可信任的人陪着你。</p>
          <a className="btn full" href="tel:12356"><Icon name="phone" /> 拨打心理援助热线 12356</a>
          <div className="crisis-actions"><a href="tel:110">立即危险：110</a><a href="tel:120">医疗急救：120</a></div>
          <Notice warm>如果你已有明确计划、工具或无法保证安全，请不要等待在线回复，立即联系 110/120。</Notice>
          <Button kind="ghost" full onClick={onClose}>我现在有人陪伴，返回对话</Button>
        </div>
      </div>
    </div>
  )
}

export function ConversationHistory() {
  const [items, setItems] = useState<Array<{ id: string; title: string; summary: string; createdAt: number }>>([])
  useEffect(() => { void repository.list<typeof items[number]>('chat-summary', 1, 30).then((result) => setItems(result.items)) }, [])
  return (
    <>
      <PageHeader title="历史摘要" subtitle="只展示已授权保存的对话" back />
      <div className="scroll-area stack">
        {!items.length ? <EmptyState title="还没有历史摘要" text="当你允许保存聊天后，U2 会在本机生成简短摘要。" /> : items.map((item) => (
          <div className="card" key={item.id}><strong>{item.title}</strong><p className="summary-text">{item.summary}</p><small className="muted">{new Date(item.createdAt).toLocaleString('zh-CN')}</small></div>
        ))}
      </div>
    </>
  )
}
