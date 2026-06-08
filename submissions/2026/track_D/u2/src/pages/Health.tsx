import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { AssessmentKind, AssessmentRecord, HealthEntry, LabMetric, MedicationLog, MedicationPlan, ReportAnalysis, ReportRecord, RiskKind, TimelineEvent } from '../types'
import { FeatureRow, PageHeader, Sheet } from '../components/AppShell'
import { Button, CardTag, Chip, EmptyState, Notice, SectionLabel } from '../components/UI'
import { Icon } from '../components/Icon'
import { repository } from '../data/repository'
import { ASSESSMENTS, ASSESSMENT_OPTIONS, scoreAssessment } from '../services/assessments'
import { evaluateRisk, RISK_QUESTIONS } from '../services/risk'
import { extractReport, explainMetrics } from '../services/reports'
import { reminderAdapter } from '../services/reminders'
import { useAppStore } from '../store/appStore'
import { useChatStore } from '../store/chatStore'
import { fileToDataUrl, formatDate, todayKey, uid } from '../utils'

function useRecords<T>(type: string, pageSize = 100) {
  const [items, setItems] = useState<T[]>([])
  const [version, setVersion] = useState(0)
  const reload = () => setVersion((value) => value + 1)
  useEffect(() => { void repository.list<T>(type, 1, pageSize).then((result) => setItems(result.items)) }, [type, pageSize, version])
  return [items, reload] as const
}

async function addTimeline(category: TimelineEvent['category'], title: string, summary: string, refId?: string) {
  await repository.save('timeline', { id: uid('timeline'), category, title, summary, createdAt: Date.now(), refId })
}

export default function HealthPage() {
  const navigate = useNavigate()
  const [entries] = useRecords<HealthEntry>('health-entry')
  const [plans] = useRecords<MedicationPlan>('medication-plan')
  const [logs] = useRecords<MedicationLog>('medication-log')
  const [metrics] = useRecords<LabMetric>('lab-metric')
  const [reports] = useRecords<ReportRecord>('report')
  const [assessments] = useRecords<AssessmentRecord>('assessment')
  const today = todayKey()
  const todayEntry = entries.find((entry) => entry.date === today)
  const latestMetric = [...metrics].sort((a, b) => b.date.localeCompare(a.date))[0]
  const activePlan = plans.find((plan) => plan.active)
  const takenToday = logs.some((log) => log.date === today && log.status === 'taken')
  const monthDays = buildCalendarDays(new Date())

  return (
    <>
      <PageHeader title="健康" subtitle="记录、趋势与复诊准备" settings />
      <div className="scroll-area health-home">
        <section className="daily-quote">
          <small>{new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' }).format(new Date())}</small>
          <h1>今天也在好好生活</h1>
          <p>“把今天照顾好，本身就是一种向前。”</p>
        </section>

        <section className="health-snapshot">
          <div><span>服药</span><strong>{activePlan ? (takenToday ? '已完成' : '待确认') : '未设置'}</strong></div>
          <div><span>睡眠</span><strong>{todayEntry?.sleepHours ? `${todayEntry.sleepHours}h` : '待记录'}</strong></div>
          <div><span>病载</span><strong>{latestMetric?.viralLoadText || '暂无'}</strong></div>
        </section>

        <div className="card calendar-card">
          <div className="row"><div><strong>{new Date().getFullYear()} 年 {new Date().getMonth() + 1} 月</strong><small>点亮每一次照顾自己的行动</small></div><span className="grow" /><button className="mini-link" onClick={() => navigate('/health/timeline')}>时间线</button></div>
          <div className="calendar-grid weekdays">{'一二三四五六日'.split('').map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-grid">
            {monthDays.map((day, index) => <span key={`${day}-${index}`} className={`${day === new Date().getDate() ? 'today' : ''} ${day && entries.some((entry) => Number(entry.date.slice(-2)) === day) ? 'recorded' : ''}`}>{day || ''}</span>)}
          </div>
        </div>

        <div className="dashboard-grid">
          <button className="dashboard-tile" onClick={() => navigate('/health/medications')}><Icon name="pill" /><strong>用药提醒</strong><small>{activePlan ? `${activePlan.name} · ${activePlan.times.join(' / ')}` : '设置每日计划'}</small></button>
          <button className="dashboard-tile" onClick={() => navigate('/health/log')}><Icon name="edit" /><strong>健康日记</strong><small>{todayEntry ? '今天已记录' : '记录睡眠与状态'}</small></button>
          <button className="dashboard-tile" onClick={() => navigate('/health/assessments')}><Icon name="breath" /><strong>心理测评</strong><small>{assessments[0] ? `${assessments[0].kind} · ${assessments[0].score} 分` : 'PHQ-9 · GAD-7'}</small></button>
          <button className="dashboard-tile" onClick={() => navigate('/health/risk')}><Icon name="shield" /><strong>HIV 风险评估</strong><small>PEP · 常态分流</small></button>
        </div>

        <div className="card stack">
          <div className="row"><CardTag>指标趋势</CardTag><span className="grow" /><button className="mini-link" onClick={() => navigate('/health/trends')}>查看全部</button></div>
          <div className="metric-pair">
            <div><span>CD4</span><strong>{latestMetric?.cd4 ?? '—'}</strong><small>cells/μL</small></div>
            <div><span>病毒载量</span><strong>{latestMetric?.viralLoadText || '—'}</strong></div>
          </div>
          <p className="summary-text">{explainMetrics(metrics)}</p>
        </div>

        <FeatureRow icon="doc" title="病历与报告" text={reports[0] ? `${reports[0].analysis.reportType} · ${reports[0].analysis.testDate}` : '拍照、图片、PDF 或手动录入'} onClick={() => navigate('/health/reports')} right={<span className="count-badge">{reports.length}</span>} />
        <Notice>健康记录与分析只用于就医沟通辅助，不替代医生判断，也不会建议你自行停药、换药或调整剂量。</Notice>
      </div>
    </>
  )
}

function buildCalendarDays(date: Date) {
  const year = date.getFullYear()
  const month = date.getMonth()
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7
  const count = new Date(year, month + 1, 0).getDate()
  return [...Array(offset).fill(0), ...Array.from({ length: count }, (_, index) => index + 1)]
}

export function HealthLogPage() {
  const navigate = useNavigate()
  const messages = useChatStore((state) => state.messages)
  const showToast = useAppStore((state) => state.showToast)
  const [date, setDate] = useState(todayKey())
  const [sleepHours, setSleep] = useState('')
  const [weight, setWeight] = useState('')
  const [symptoms, setSymptoms] = useState<string[]>([])
  const [note, setNote] = useState('')
  const symptomOptions = ['疲乏', '头痛', '恶心', '皮疹', '发热', '无明显不适']

  function draftFromChat() {
    const today = messages.filter((message) => new Date(message.createdAt).toISOString().slice(0, 10) === todayKey())
    const userText = today.filter((message) => message.role === 'user').map((message) => message.content).filter((text) => !text.includes('健康摘要'))
    if (!userText.length) return showToast('今天还没有可整理的聊天内容')
    setNote(`今天和 U2 聊到：${userText.slice(-3).join('；')}`)
    showToast('已生成日记草稿，请确认后保存')
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    const entry: HealthEntry = { id: uid('health'), date, sleepHours: sleepHours ? Number(sleepHours) : null, weight: weight ? Number(weight) : null, symptoms, note, createdAt: Date.now() }
    await repository.save('health-entry', entry)
    await addTimeline('健康', '健康日记', `${sleepHours ? `睡眠 ${sleepHours}h · ` : ''}${symptoms.join('、') || '已记录今日状态'}`, entry.id)
    showToast('健康日记已保存在本机')
    navigate('/health')
  }

  return (
    <>
      <PageHeader title="健康日记" subtitle="只记录你愿意留下的部分" back />
      <form className="scroll-area stack form-page" onSubmit={(event) => void save(event)}>
        <label className="form-label">日期<input className="field" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <div className="two-fields">
          <label className="form-label">睡眠（小时）<input className="field" inputMode="decimal" value={sleepHours} onChange={(event) => setSleep(event.target.value)} placeholder="7.5" /></label>
          <label className="form-label">体重（kg）<input className="field" inputMode="decimal" value={weight} onChange={(event) => setWeight(event.target.value)} placeholder="可留空" /></label>
        </div>
        <label className="form-label">今天的身体感受<div className="chip-grid">{symptomOptions.map((item) => <Chip key={item} active={symptoms.includes(item)} onClick={() => setSymptoms((items) => items.includes(item) ? items.filter((value) => value !== item) : [...items, item])}>{item}</Chip>)}</div></label>
        <label className="form-label">日记<div className="row" style={{ marginBottom: 8 }}><span className="grow" /><button type="button" className="mini-link ai-draft" onClick={draftFromChat}><Icon name="spark" size={14} /> 整理今日聊天</button></div><textarea className="field diary-field" value={note} onChange={(event) => setNote(event.target.value)} placeholder="写下今天发生的事、感受或想在复诊时问的问题…" /></label>
        <Notice>“整理今日聊天”只生成可编辑草稿，不会自动推断症状、情绪或保存结构化数据。</Notice>
        <Button full type="submit">保存日记</Button>
      </form>
    </>
  )
}

export function MedicationPage() {
  const [plans, reloadPlans] = useRecords<MedicationPlan>('medication-plan')
  const [logs, reloadLogs] = useRecords<MedicationLog>('medication-log')
  const [open, setOpen] = useState(false)
  const showToast = useAppStore((state) => state.showToast)
  const today = todayKey()

  async function mark(plan: MedicationPlan, time: string) {
    const existing = logs.find((log) => log.planId === plan.id && log.date === today && log.scheduledTime === time)
    const log: MedicationLog = { id: existing?.id ?? uid('medlog'), planId: plan.id, date: today, scheduledTime: time, status: 'taken', confirmedAt: Date.now() }
    await repository.save('medication-log', { ...log, createdAt: log.confirmedAt })
    await addTimeline('用药', `已服用 ${plan.name}`, `${time} · ${plan.dose}`, log.id)
    reloadLogs()
    showToast('已记录本次服药')
  }

  return (
    <>
      <PageHeader title="用药提醒" subtitle="网页关闭后通知可能受浏览器限制" back action={<button className="icon-button" onClick={() => setOpen(true)}><Icon name="plus" /></button>} />
      <div className="scroll-area stack">
        <Notice>浏览器通知需要授权，且后台提醒能力取决于系统。建议同时导出到系统日历。</Notice>
        {!plans.length ? <EmptyState icon="pill" title="还没有用药计划" text="添加药名、剂量和时间，U2 会生成每日确认入口。" action={<Button onClick={() => setOpen(true)}>添加计划</Button>} /> : plans.map((plan) => (
          <div className="card stack" key={plan.id}>
            <div className="row"><span className="feature-icon"><Icon name="pill" /></span><div className="grow"><strong>{plan.name}</strong><small className="block muted">{plan.dose} · {plan.requirement || '按医嘱'}</small></div><button className="mini-link" onClick={() => reminderAdapter.exportMedication(plan)}>导出日历</button></div>
            {plan.times.map((time) => {
              const done = logs.some((log) => log.planId === plan.id && log.date === today && log.scheduledTime === time && log.status === 'taken')
              return <button key={time} className={`dose-row ${done ? 'done' : ''}`} onClick={() => void mark(plan, time)}><Icon name={done ? 'check' : 'clock'} /><span className="grow">{time}</span><strong>{done ? '已服用' : '确认服药'}</strong></button>
            })}
            <Button kind="ghost" small onClick={() => void reminderAdapter.requestPermission().then((result) => showToast(result === 'granted' ? '浏览器通知已开启' : '未开启通知，可使用日历提醒'))}><Icon name="bell" /> 开启浏览器通知</Button>
          </div>
        ))}
      </div>
      {open && <MedicationSheet onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reloadPlans(); showToast('用药计划已添加') }} />}
    </>
  )
}

function MedicationSheet({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('')
  const [dose, setDose] = useState('')
  const [time, setTime] = useState('21:00')
  const [requirement, setRequirement] = useState('')
  async function save() {
    if (!name || !dose) return
    await repository.save('medication-plan', { id: uid('med'), name, dose, times: [time], requirement, active: true, createdAt: Date.now() })
    onSaved()
  }
  return <Sheet title="添加用药计划" onClose={onClose}><div className="stack"><label className="form-label">药物名称<input className="field" value={name} onChange={(event) => setName(event.target.value)} /></label><label className="form-label">剂量<input className="field" value={dose} onChange={(event) => setDose(event.target.value)} placeholder="例如：1 片" /></label><label className="form-label">每日时间<input className="field" type="time" value={time} onChange={(event) => setTime(event.target.value)} /></label><label className="form-label">服用要求<input className="field" value={requirement} onChange={(event) => setRequirement(event.target.value)} placeholder="例如：随餐，按医嘱" /></label><Button full disabled={!name || !dose} onClick={() => void save()}>保存计划</Button></div></Sheet>
}

export function TrendsPage() {
  const [metrics, reload] = useRecords<LabMetric>('lab-metric')
  const [entries] = useRecords<HealthEntry>('health-entry')
  const [open, setOpen] = useState(false)
  const sorted = [...metrics].sort((a, b) => a.date.localeCompare(b.date))
  return (
    <>
      <PageHeader title="数据趋势" subtitle="趋势比单次结果更有参考意义" back action={<button className="icon-button" onClick={() => setOpen(true)}><Icon name="plus" /></button>} />
      <div className="scroll-area stack">
        <div className="card stack"><div className="row"><CardTag>病毒载量 / CD4</CardTag><span className="grow" /><small className="muted">{metrics.length} 次记录</small></div><SimpleChart metrics={sorted} /><p className="summary-text">{explainMetrics(metrics)}</p></div>
        <div className="card stack"><SectionLabel>最近健康状态</SectionLabel>{entries.slice(0, 5).map((entry) => <div className="history-line" key={entry.id}><strong>{formatDate(entry.date)}</strong><span>{entry.sleepHours ? `睡眠 ${entry.sleepHours}h` : '未记睡眠'}</span><small>{entry.symptoms.join('、') || '无明显不适'}</small></div>)}{!entries.length && <p className="muted">暂无健康日记。</p>}</div>
        <Notice>图表仅帮助你整理变化。感染、疫苗、检测误差等都可能影响单次结果，请与医生一起解读。</Notice>
      </div>
      {open && <MetricSheet onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload() }} />}
    </>
  )
}

function SimpleChart({ metrics }: { metrics: LabMetric[] }) {
  if (!metrics.length) return <div className="chart-empty">录入指标后，这里会显示日期和趋势</div>
  const width = 320
  const height = 150
  const maxCd4 = Math.max(...metrics.map((item) => item.cd4 ?? 0), 800)
  const points = metrics.map((item, index) => `${20 + index * ((width - 40) / Math.max(1, metrics.length - 1))},${height - 28 - ((item.cd4 ?? 0) / maxCd4) * (height - 52)}`).join(' ')
  return <div className="chart-wrap"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="CD4 趋势图"><line x1="20" y1={height - 28} x2={width - 20} y2={height - 28} stroke="var(--line)" /><polyline points={points} fill="none" stroke="var(--brand)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />{metrics.map((item, index) => { const [x, y] = points.split(' ')[index].split(','); return <g key={item.id}><circle cx={x} cy={y} r="4" fill="var(--brand)" /><text x={x} y={height - 8} textAnchor="middle" fontSize="9" fill="var(--faint)">{item.date.slice(5)}</text></g> })}</svg></div>
}

function MetricSheet({ onClose, onSaved, initial }: { onClose: () => void; onSaved: () => void; initial?: Partial<LabMetric> }) {
  const [date, setDate] = useState(initial?.date ?? todayKey())
  const [cd4, setCd4] = useState(initial?.cd4?.toString() ?? '')
  const [viralLoadText, setViralLoadText] = useState(initial?.viralLoadText ?? '')
  const [institution, setInstitution] = useState(initial?.institution ?? '')
  async function save() {
    const numeric = viralLoadText.match(/\d[\d,]*/)?.[0].replaceAll(',', '')
    const metric: LabMetric = { id: uid('metric'), date, cd4: cd4 ? Number(cd4) : null, viralLoad: numeric ? Number(numeric) : null, viralLoadText, institution, source: initial?.source ?? 'manual', createdAt: Date.now() }
    await repository.save('lab-metric', metric)
    await addTimeline('医疗', '记录复查指标', `CD4 ${cd4 || '—'} · 病载 ${viralLoadText || '—'}`, metric.id)
    onSaved()
  }
  return <Sheet title="记录复查指标" onClose={onClose}><div className="stack"><label className="form-label">检测日期<input className="field" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label><label className="form-label">CD4（cells/μL）<input className="field" inputMode="numeric" value={cd4} onChange={(event) => setCd4(event.target.value)} /></label><label className="form-label">病毒载量原文<input className="field" value={viralLoadText} onChange={(event) => setViralLoadText(event.target.value)} placeholder="例如：未检出 / <20 copies/mL" /></label><label className="form-label">医院 / 机构<input className="field" value={institution} onChange={(event) => setInstitution(event.target.value)} /></label><Button full onClick={() => void save()}>确认保存</Button></div></Sheet>
}

export function AssessmentPicker() {
  const navigate = useNavigate()
  const [records] = useRecords<AssessmentRecord>('assessment')
  return <><PageHeader title="心理测评" subtitle="固定完整量表 · 不是诊断" back /><div className="scroll-area stack"><FeatureRow icon="moon" title="PHQ-9 抑郁筛查" text="9 题 · 了解近两周的心境" onClick={() => navigate('/health/assessment/PHQ-9')} /><FeatureRow icon="breath" title="GAD-7 焦虑筛查" text="7 题 · 了解近两周的焦虑" onClick={() => navigate('/health/assessment/GAD-7')} /><SectionLabel>历史结果</SectionLabel>{records.map((record) => <div className="card row" key={record.id}><div className="grow"><strong>{record.kind} · {record.score} 分</strong><small className="block muted">{record.level}区间 · {formatDate(record.createdAt)}</small></div>{record.selfHarmRisk && <CardTag warm>需优先支持</CardTag>}</div>)}{!records.length && <p className="muted">尚未完成测评。</p>}<Notice>量表结果只反映近期主观感受。若状态持续、加重或影响生活，建议联系专业人员。</Notice></div></>
}

export function AssessmentPage() {
  const navigate = useNavigate()
  const kind = (useParams().kind === 'PHQ-9' ? 'PHQ-9' : 'GAD-7') as AssessmentKind
  const bank = ASSESSMENTS[kind]
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Array<number | null>>(Array(bank.questions.length).fill(null))
  const [result, setResult] = useState<ReturnType<typeof scoreAssessment> | null>(null)
  async function finish() {
    const score = scoreAssessment(kind, answers as number[])
    const record: AssessmentRecord = { id: uid('assessment'), kind, answers: answers as number[], ...score, createdAt: Date.now() }
    await repository.save('assessment', record)
    await addTimeline('测评', `${kind} 自评`, `${score.score} 分 · ${score.level}区间`, record.id)
    setResult(score)
  }
  if (result) return <><PageHeader title="测评结果" back /><div className="scroll-area stack"><div className="result-card card"><CardTag>{kind}</CardTag><strong>{result.score}</strong><span>/ {kind === 'PHQ-9' ? 27 : 21} 分 · {result.level}区间</span></div>{result.selfHarmRisk && <div className="card crisis-inline"><strong>你不需要一个人扛着</strong><p>第 9 题提示需要优先关注安全。请联系 12356；如有明确计划或无法保证安全，立即拨打 110/120。</p><a className="btn full" href="tel:12356">拨打 12356</a></div>}<Notice>这不是诊断结果。你可以把结果带给心理咨询师、精神科或感染科医护讨论。</Notice><Button onClick={() => navigate('/companion')}>和 U2 聊聊结果</Button></div></>
  return <><PageHeader title={`${kind} 自评`} subtitle={bank.description} back /><div className="assessment-progress"><span>第 {index + 1} / {bank.questions.length} 题</span><i><b style={{ width: `${((index + 1) / bank.questions.length) * 100}%` }} /></i></div><div className="scroll-area assessment-body"><h2>过去两周里，你有多少时候<br />{bank.questions[index]}？</h2><div className="stack">{ASSESSMENT_OPTIONS.map((option, value) => <button key={option} className={`answer-card ${answers[index] === value ? 'active' : ''}`} onClick={() => setAnswers((items) => items.map((item, itemIndex) => itemIndex === index ? value : item))}><i>{answers[index] === value && <Icon name="check" size={13} />}</i><strong className="grow">{option}</strong><small>{value} 分</small></button>)}</div><Notice>请选择最接近你实际感受的一项，不需要追求“正确答案”。</Notice></div><div className="flow-actions"><Button kind="ghost" onClick={() => index ? setIndex(index - 1) : navigate(-1)}>{index ? '上一题' : '退出'}</Button><Button disabled={answers[index] === null} onClick={() => index === bank.questions.length - 1 ? void finish() : setIndex(index + 1)}>{index === bank.questions.length - 1 ? '查看结果' : '下一题'}</Button></div></>
}

export function RiskPage() {
  const [kind, setKind] = useState<RiskKind>('pep')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<ReturnType<typeof evaluateRisk> | null>(null)
  const bank = RISK_QUESTIONS[kind]
  function changeKind(next: RiskKind) { setKind(next); setAnswers({}); setResult(null) }
  async function finish() {
    const urgency = evaluateRisk(kind, answers)
    const record = { id: uid('risk'), kind, answers, urgency, createdAt: Date.now() }
    await repository.save('risk', record)
    await addTimeline('医疗', kind === 'pep' ? 'PEP 暴露后评估' : 'HIV 常态风险评估', urgency === 'urgent' ? '建议立即就医评估' : urgency === 'consult' ? '建议咨询与检测' : '未发现明显紧急信号', record.id)
    setResult(urgency)
  }
  return <><PageHeader title="HIV 风险评估" subtitle="轻分流 · 非检测 · 非诊断" back /><div className="segmented risk-tabs"><button className={kind === 'pep' ? 'active' : ''} onClick={() => changeKind('pep')}>PEP 暴露后</button><button className={kind === 'general' ? 'active' : ''} onClick={() => changeKind('general')}>常态评估</button></div><div className="scroll-area stack">{result ? <RiskResult urgency={result} kind={kind} reset={() => setResult(null)} /> : <><Notice warm={kind === 'pep'}>{kind === 'pep' ? '如果暴露发生在 72 小时内，请不要等待线上结果，尽快联系感染科、急诊或疾控评估 PEP。' : '本流程只帮助梳理下一步，不输出感染概率。'}</Notice>{bank.map((item, index) => <div className="card stack" key={item.key}><strong>{index + 1} · {item.question}</strong><div className="chip-grid">{item.options.map((option) => <Chip key={option} active={answers[item.key] === option} onClick={() => setAnswers((values) => ({ ...values, [item.key]: option }))}>{option}</Chip>)}</div></div>)}<Button full disabled={Object.keys(answers).length !== bank.length} onClick={() => void finish()}>查看评估建议</Button></>}</div></>
}

function RiskResult({ urgency, kind, reset }: { urgency: 'low' | 'consult' | 'urgent'; kind: RiskKind; reset: () => void }) {
  const navigate = useNavigate()
  const title = urgency === 'urgent' ? '建议立即就医评估' : urgency === 'consult' ? '建议安排咨询与检测' : '未发现明显紧急信号'
  const text = urgency === 'urgent' ? '你的回答提示存在需要专业人员尽快评估的暴露情形。PEP 越早开始越好，请优先行动。' : urgency === 'consult' ? '你的回答中有需要进一步核实的情况。建议按合适时间接受规范检测并咨询专业人员。' : '这不代表排除感染。若暴露时间、方式或对方状态仍不确定，仍可咨询专业人员。'
  return <><div className={`card risk-result ${urgency}`}><Icon name={urgency === 'urgent' ? 'clock' : 'shield'} size={30} /><h2>{title}</h2><p>{text}</p>{kind === 'pep' && urgency === 'urgent' && <a className="btn full" href="tel:120">联系急诊 / 120</a>}</div><Notice>本评估不会判断你是否感染 HIV，也不会推荐个体用药。确诊只能依靠规范检测。</Notice><Button onClick={() => navigate('/support/care')}>准备检测 / 就医</Button><Button kind="ghost" onClick={() => navigate('/companion')}>我很紧张，想聊聊</Button><Button kind="ghost" onClick={reset}>重新评估</Button></>
}

export function ReportPage() {
  const navigate = useNavigate()
  const [reports] = useRecords<ReportRecord>('report')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<ReportRecord | null>(null)
  const pageSize = 5
  const filtered = reports.filter((report) => !query || report.analysis.testDate.includes(query) || report.analysis.institution.includes(query))
  const shown = filtered.slice((page - 1) * pageSize, page * pageSize)
  return <><PageHeader title="病历与报告" subtitle="本地保存 · 保存前需确认" back action={<button className="icon-button" onClick={() => navigate('/health/reports/upload')}><Icon name="plus" /></button>} /><div className="scroll-area stack"><div className="search-box"><Icon name="search" /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="按日期或机构搜索" /></div>{shown.map((report) => <button className="card report-row" key={report.id} onClick={() => setSelected(report)}><span className="report-icon"><Icon name="doc" /></span><span className="grow"><strong>{report.analysis.reportType}</strong><small>{report.analysis.testDate} · {report.analysis.institution || '未填写机构'}</small><p>{report.analysis.viralLoadText || (report.analysis.cd4 ? `CD4 ${report.analysis.cd4}` : '已归档，待补充指标')}</p></span><Icon name="chevron" /></button>)}{!shown.length && <EmptyState icon="doc" title="还没有病历记录" text="可以上传图片、PDF，或手动确认报告字段。" action={<Button onClick={() => navigate('/health/reports/upload')}>添加报告</Button>} />} {filtered.length > pageSize && <div className="pagination"><Button small kind="ghost" disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</Button><span>{page} / {Math.ceil(filtered.length / pageSize)}</span><Button small kind="ghost" disabled={page >= Math.ceil(filtered.length / pageSize)} onClick={() => setPage(page + 1)}>下一页</Button></div>}<Notice>原始文件和提取字段都只保存在本机。请始终对照原报告确认。</Notice></div>{selected && <Sheet title="报告详情" onClose={() => setSelected(null)}><div className="stack"><CardTag>{selected.analysis.reportType}</CardTag><h2>{selected.analysis.testDate}</h2><div className="metric-pair"><div><span>CD4</span><strong>{selected.analysis.cd4 ?? '—'}</strong></div><div><span>病毒载量</span><strong>{selected.analysis.viralLoadText || '—'}</strong></div></div><SectionLabel>本地识别原文</SectionLabel><div className="long-text">{selected.analysis.ocrText}</div><SectionLabel>沟通辅助</SectionLabel><p className="summary-text">{selected.analysis.explanation}</p>{selected.analysis.doctorQuestions.map((question) => <div className="notice" key={question}>{question}</div>)}</div></Sheet>}</>
}

export function ReportUploadPage() {
  const navigate = useNavigate()
  const showToast = useAppStore((state) => state.showToast)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [analysis, setAnalysis] = useState<ReportAnalysis | null>(null)
  const [busy, setBusy] = useState(false)
  async function pick(selected?: File) {
    if (!selected) return
    if (selected.size > 8 * 1024 * 1024) return showToast('单个文件请控制在 8MB 以内')
    setFile(selected)
    setPreview(selected.type.startsWith('image/') ? await fileToDataUrl(selected) : '')
    setBusy(true)
    setAnalysis(await extractReport(selected))
    setBusy(false)
  }
  async function save() {
    if (!file || !analysis) return
    const record: ReportRecord = { id: uid('report'), fileName: file.name, mimeType: file.type, fileData: preview || undefined, analysis, createdAt: Date.now() }
    await repository.save('report', record)
    if (analysis.cd4 !== null || analysis.viralLoadText) {
      await repository.save('lab-metric', { id: uid('metric'), date: analysis.testDate, cd4: analysis.cd4, viralLoad: analysis.viralLoad, viralLoadText: analysis.viralLoadText, institution: analysis.institution, source: 'report', createdAt: Date.now() })
    }
    await addTimeline('医疗', '新增病历报告', `${analysis.reportType} · ${analysis.testDate}`, record.id)
    showToast('报告已保存到本机')
    navigate('/health/reports')
  }
  return <><PageHeader title="添加病历报告" subtitle="图片 / PDF / 手动确认" back /><div className="scroll-area stack">{!file && <label className="upload-zone"><Icon name="upload" size={30} /><strong>拍照或选择报告</strong><span>支持 JPG、PNG、PDF，最大 8MB</span><input type="file" accept="image/*,application/pdf" capture="environment" onChange={(event) => void pick(event.target.files?.[0])} /></label>}{file && <><div className="card file-preview">{preview ? <img src={preview} alt="报告预览" /> : <Icon name="file" size={48} />}<div><strong>{file.name}</strong><small>{Math.round(file.size / 1024)} KB</small></div></div>{busy && <div className="card center"><span className="orb spin" /><strong>正在尝试本地识别…</strong></div>}{analysis && <div className="stack"><Notice>{analysis.ocrText}</Notice><label className="form-label">报告类型<input className="field" value={analysis.reportType} onChange={(event) => setAnalysis({ ...analysis, reportType: event.target.value })} /></label><label className="form-label">检测日期<input className="field" type="date" value={analysis.testDate} onChange={(event) => setAnalysis({ ...analysis, testDate: event.target.value })} /></label><label className="form-label">医院 / 机构<input className="field" value={analysis.institution} onChange={(event) => setAnalysis({ ...analysis, institution: event.target.value })} /></label><div className="two-fields"><label className="form-label">CD4<input className="field" inputMode="numeric" value={analysis.cd4 ?? ''} onChange={(event) => setAnalysis({ ...analysis, cd4: event.target.value ? Number(event.target.value) : null })} /></label><label className="form-label">病毒载量<input className="field" value={analysis.viralLoadText} onChange={(event) => { const value = event.target.value; const numeric = value.match(/\d[\d,]*/)?.[0].replaceAll(',', ''); setAnalysis({ ...analysis, viralLoadText: value, viralLoad: numeric ? Number(numeric) : null }) }} /></label></div><Notice warm>请对照原报告逐项确认。识别结果可能出错，只有确认后的字段才会进入趋势。</Notice><Button full onClick={() => void save()}>确认字段并保存</Button></div>}</>}</div></>
}

export function TimelinePage() {
  const [events] = useRecords<TimelineEvent>('timeline')
  return <><PageHeader title="健康时间线" subtitle="把分散记录放在同一条线上" back /><div className="scroll-area timeline">{events.map((event) => <div className="timeline-item" key={event.id}><span className="timeline-dot" /><div><small>{formatDate(event.createdAt, true)} · {event.category}</small><strong>{event.title}</strong><p>{event.summary}</p></div></div>)}{!events.length && <EmptyState icon="history" title="时间线还是空的" text="日记、用药、测评、指标和正念记录会自动汇集到这里。" />}</div></>
}
