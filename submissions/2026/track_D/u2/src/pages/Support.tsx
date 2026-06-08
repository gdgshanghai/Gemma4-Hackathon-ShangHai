import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FavoriteRecord, KnowledgeArticle, NewsItem } from '../types'
import { KNOWLEDGE, LOCAL_NEWS } from '../content/knowledge'
import { FeatureRow, PageHeader, Sheet } from '../components/AppShell'
import { Button, CardTag, Chip, Notice, SectionLabel } from '../components/UI'
import { Icon } from '../components/Icon'
import { repository } from '../data/repository'
import { fetchNews } from '../services/news'
import { useAppStore } from '../store/appStore'
import { uid } from '../utils'

export default function SupportPage() {
  const navigate = useNavigate()
  const [favorites, setFavorites] = useState<FavoriteRecord[]>([])
  useEffect(() => { void repository.list<FavoriteRecord>('favorite', 1, 100).then((result) => setFavorites(result.items)) }, [])
  return (
    <>
      <PageHeader title="支持" subtitle="知识、练习与求助资源" settings />
      <div className="scroll-area support-home">
        <section className="support-hero">
          <span className="feature-icon"><Icon name="book" size={24} /></span>
          <div><small>本地知识库</small><h1>了解得更清楚，<br />心里就多一点余地。</h1></div>
        </section>
        <button className="news-banner" onClick={() => navigate('/support/news')}>
          <div><CardTag warm>需主动联网</CardTag><strong>前沿讯息</strong><small>只有点击后才会请求公开资讯</small></div><Icon name="wifi" />
        </button>
        <SectionLabel>知识与行动</SectionLabel>
        <div className="dashboard-grid support-grid">
          <button className="dashboard-tile" onClick={() => navigate('/support/knowledge')}><Icon name="book" /><strong>U=U 知识</strong><small>{favorites.length} 篇收藏</small></button>
          <button className="dashboard-tile" onClick={() => navigate('/support/care')}><Icon name="doc" /><strong>检测 / 就医</strong><small>流程与问题清单</small></button>
          <button className="dashboard-tile" onClick={() => navigate('/support/mindfulness')}><Icon name="leaf" /><strong>正念练习</strong><small>呼吸 · 睡前 · 急救</small></button>
          <button className="dashboard-tile" onClick={() => navigate('/support/resources')}><Icon name="phone" /><strong>求助资源</strong><small>12356 · 110 · 120</small></button>
        </div>
        <SectionLabel>推荐阅读</SectionLabel>
        {KNOWLEDGE.slice(0, 3).map((article) => <FeatureRow key={article.id} icon="book" title={article.title} text={article.summary} onClick={() => navigate('/support/knowledge')} />)}
        <Notice>本地知识条目标注来源和更新时间；涉及个人治疗决定时，请与医生确认。</Notice>
      </div>
    </>
  )
}

export function KnowledgePage() {
  const [category, setCategory] = useState('全部')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<KnowledgeArticle | null>(null)
  const [favorites, setFavorites] = useState<FavoriteRecord[]>([])
  const showToast = useAppStore((state) => state.showToast)
  const categories = ['全部', ...new Set(KNOWLEDGE.map((article) => article.category))]
  const filtered = useMemo(() => KNOWLEDGE.filter((article) => (category === '全部' || article.category === category) && (!query || `${article.title}${article.summary}${article.content}`.includes(query))), [category, query])
  async function loadFavorites() { setFavorites((await repository.list<FavoriteRecord>('favorite', 1, 100)).items) }
  useEffect(() => { void loadFavorites() }, [])
  async function toggleFavorite(articleId: string) {
    const existing = favorites.find((item) => item.articleId === articleId)
    if (existing) await repository.remove(existing.id)
    else await repository.save('favorite', { id: uid('favorite'), articleId, createdAt: Date.now() })
    await loadFavorites()
    showToast(existing ? '已取消收藏' : '已收藏到本机')
  }
  return <><PageHeader title="U=U 知识库" subtitle="本地可读 · 带来源" back /><div className="scroll-area stack"><div className="search-box"><Icon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 U=U、PEP、CD4…" /></div><div className="quick-strip inside">{categories.map((item) => <Chip key={item} active={category === item} onClick={() => setCategory(item)}>{item}</Chip>)}</div>{filtered.map((article) => <button className="card knowledge-card" key={article.id} onClick={() => setSelected(article)}><div className="row"><CardTag>{article.category}</CardTag><span className="grow" />{favorites.some((item) => item.articleId === article.id) && <Icon name="star" size={16} style={{ color: 'var(--warm)' }} />}</div><strong>{article.title}</strong><p>{article.summary}</p><small>{article.source} · 更新于 {article.updatedAt}</small></button>)}</div>{selected && <Sheet title={selected.title} onClose={() => setSelected(null)}><article className="article stack"><CardTag>{selected.category}</CardTag><p>{selected.content}</p><Notice>来源：{selected.source} · 更新于 {selected.updatedAt}</Notice><Button kind={favorites.some((item) => item.articleId === selected.id) ? 'soft' : 'primary'} onClick={() => void toggleFavorite(selected.id)}><Icon name="star" /> {favorites.some((item) => item.articleId === selected.id) ? '已收藏' : '收藏到本机'}</Button><a className="btn ghost full" href={selected.sourceUrl} target="_blank" rel="noreferrer">查看官方来源</a></article></Sheet>}</>
}

export function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>(LOCAL_NEWS)
  const [status, setStatus] = useState<'local' | 'loading' | 'online'>('local')
  const [selected, setSelected] = useState<NewsItem | null>(null)
  async function refresh() {
    setStatus('loading')
    const result = await fetchNews('treatment')
    setItems(result.items)
    setStatus(result.online ? 'online' : 'local')
  }
  return <><PageHeader title="前沿讯息" subtitle="仅请求公开内容，不上传健康数据" back action={<button className="icon-button" disabled={status === 'loading'} onClick={() => void refresh()}><Icon name="refresh" className={status === 'loading' ? 'spin' : ''} /></button>} /><div className="scroll-area stack"><Notice>{status === 'online' ? '已获取公开资讯。请求中未包含聊天或健康数据。' : '当前展示本地缓存。点击右上角刷新才会联网。'}</Notice>{items.map((item) => <button className="card knowledge-card" key={item.id} onClick={() => setSelected(item)}><div className="row"><CardTag warm>{item.topic}</CardTag><span className="grow" /><small>{item.source}</small></div><strong>{item.title}</strong><p>{item.summary}</p><small>发布于 {item.publishedAt}</small></button>)}</div>{selected && <Sheet title={selected.title} onClose={() => setSelected(null)}><div className="stack"><p className="article-text">{selected.summary}</p><Notice>来源：{selected.source} · 获取时间：{selected.fetchedAt}</Notice><a className="btn full" href={selected.url} target="_blank" rel="noreferrer">打开原始来源</a></div></Sheet>}</>
}

export function CareGuidePage() {
  const [step, setStep] = useState<'before' | 'visit' | 'after'>('before')
  const content = {
    before: [['整理时间线', '记下暴露日期、检测日期、目前最担心的问题'], ['准备隐私问题', '可以先询问检测流程、结果通知方式与隐私保护'], ['PEP 不等待', '若可能暴露仍在 72 小时内，优先联系感染科、急诊或疾控']],
    visit: [['可以直接表达紧张', '告诉医护“我现在很焦虑，希望先听清楚下一步”'], ['带上已有材料', '自测结果、检测报告和正在服用的药物'], ['确认下一步', '是否需要复检、何时复查、如何取得结果']],
    after: [['记录医嘱', '把医生建议写进健康时间线'], ['避免反复搜索', '优先回看医生给出的明确安排'], ['需要时求助', '焦虑持续影响睡眠和生活时，寻求心理支持']],
  }
  return <><PageHeader title="检测 / 就医准备" subtitle="把未知拆成可以行动的步骤" back /><div className="segmented care-tabs">{(['before', 'visit', 'after'] as const).map((value) => <button key={value} className={step === value ? 'active' : ''} onClick={() => setStep(value)}>{value === 'before' ? '去之前' : value === 'visit' ? '就诊中' : '回来后'}</button>)}</div><div className="scroll-area stack">{content[step].map(([title, text], index) => <div className="card guide-step" key={title}><span>{index + 1}</span><div><strong>{title}</strong><p>{text}</p></div></div>)}<div className="card stack"><SectionLabel>可以问医生</SectionLabel>{['我的检测方法和窗口期应如何理解？', '我下一次需要什么时候复查？', '哪些情况需要提前回来就诊？'].map((question) => <div className="question-row" key={question}><Icon name="check" />{question}</div>)}</div><Notice>U2 暂不直接推荐具体医院。可通过当地卫健委、疾控中心或正规医院官方渠道查询感染科与检测服务。</Notice></div></>
}

const practices = [
  { id: 'breath-3', title: '3 分钟呼吸练习', minutes: 3, text: '只把注意力放在下一次呼气' },
  { id: 'ground-5', title: '焦虑急救 · 五感落地', minutes: 5, text: '从周围能看见、听见、触到的事物开始' },
  { id: 'sleep-8', title: '睡前放松', minutes: 8, text: '让身体慢慢从警觉中退下来' },
]

export function MindfulnessPage() {
  const [selected, setSelected] = useState<typeof practices[number] | null>(null)
  const [remaining, setRemaining] = useState(0)
  const [running, setRunning] = useState(false)
  const showToast = useAppStore((state) => state.showToast)
  useEffect(() => {
    if (!running || remaining <= 0) return
    const timer = window.setInterval(() => setRemaining((value) => value - 1), 1000)
    return () => window.clearInterval(timer)
  }, [running, remaining])
  useEffect(() => {
    if (selected && remaining === 0 && running) {
      setRunning(false)
      void repository.save('mindfulness', { id: uid('mind'), title: selected.title, minutes: selected.minutes, createdAt: Date.now() })
      void repository.save('timeline', { id: uid('timeline'), category: '正念', title: selected.title, summary: `完成 ${selected.minutes} 分钟练习`, createdAt: Date.now() })
      showToast('练习完成，已经记录')
    }
  }, [remaining, running, selected, showToast])
  function start(practice: typeof practices[number]) { setSelected(practice); setRemaining(practice.minutes * 60); setRunning(true) }
  return <><PageHeader title="正念练习" subtitle="低刺激 · 可暂停 · 可记录" back /><div className="scroll-area stack">{practices.map((practice) => <FeatureRow key={practice.id} icon="leaf" title={practice.title} text={`${practice.minutes} 分钟 · ${practice.text}`} onClick={() => start(practice)} />)}<Notice>练习不能替代专业治疗；如果呼吸练习让你更不舒服，可以随时停止并把注意力转向周围环境。</Notice></div>{selected && <div className="sheet-backdrop mindfulness-backdrop"><div className="mind-player"><button className="icon-button" onClick={() => { setRunning(false); setSelected(null) }}><Icon name="close" /></button><div className={`breath-orb ${running ? 'pulse' : ''}`} /><small>{running ? '跟随自然呼吸' : '已暂停'}</small><strong>{Math.floor(remaining / 60).toString().padStart(2, '0')}:{(remaining % 60).toString().padStart(2, '0')}</strong><p>{selected.text}</p><Button onClick={() => setRunning(!running)}>{running ? '暂停' : '继续'}</Button></div></div>}</>
}

export function ResourcesPage() {
  return <><PageHeader title="求助资源" subtitle="中国大陆场景" back /><div className="scroll-area stack"><div className="card resource-main"><span><Icon name="heart" /></span><div><strong>全国统一心理援助热线</strong><h1>12356</h1><p>当情绪压力难以承受、需要专业倾听和支持时，可以拨打。</p></div><a className="btn full" href="tel:12356"><Icon name="phone" /> 立即拨打</a></div><FeatureRow icon="phone" title="110" text="有人身危险、暴力威胁或无法保证自身安全" onClick={() => { window.location.href = 'tel:110' }} /><FeatureRow icon="phone" title="120" text="需要紧急医疗救助" onClick={() => { window.location.href = 'tel:120' }} /><Notice warm>如果你有明确自伤计划、已准备工具，或身边有人正在威胁你，请优先拨打 110/120，不要等待在线回复。</Notice><SectionLabel>非紧急支持</SectionLabel><div className="card article-text">也可以联系当地精神卫生中心、综合医院心理/精神科、感染科医护，或请可信任的人陪同就诊。求助不需要等到“足够严重”。</div></div></>
}
