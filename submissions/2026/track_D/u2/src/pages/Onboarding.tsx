import { useState } from 'react'
import type { UserStatus } from '../types'
import { Button, Notice, StatusBar } from '../components/UI'
import { Icon, type IconName } from '../components/Icon'
import { useAppStore } from '../store/appStore'
import { localAI } from '../services/localAI'

const statusOptions: Array<{ value: UserStatus; icon: IconName; title: string; text: string }> = [
  { value: 'worry', icon: 'breath', title: '我担心自己可能感染', text: '想先了解风险、做个评估' },
  { value: 'test', icon: 'doc', title: '我准备检测或就诊', text: '需要准备和心理支持' },
  { value: 'diagnosed', icon: 'heart', title: '我已确诊，正在治疗', text: '需要记录、提醒和陪伴' },
  { value: 'learn', icon: 'book', title: '我只是想了解和聊聊', text: 'U=U 科普、找人说说话' },
]

export default function Onboarding() {
  const [step, setStep] = useState(0)
  const [status, setStatus] = useState<UserStatus | null>(null)
  const [saveLocal, setSaveLocal] = useState(true)
  const [saveChat, setSaveChat] = useState(true)
  const [hideEnabled, setHideEnabled] = useState(true)
  const [modelConsent, setModelConsent] = useState(true)
  const update = useAppStore((state) => state.updatePreferences)

  const finish = async () => {
    await update({ onboardingDone: true, userStatus: status, saveLocal, saveChat, hideEnabled, modelConsent })
    if (modelConsent) void localAI.initialize()
  }

  return (
    <div className="u2-screen onboarding">
      <StatusBar />
      {step > 0 && <div className="onboarding-progress">{[1, 2, 3].map((item) => <i key={item} className={item <= step ? 'active' : ''} />)}</div>}
      {step === 0 && (
        <div className="onboarding-hero enter">
          <div className="orb large pulse" />
          <h1>U2</h1>
          <h2>病毒归零，恐惧归零</h2>
          <p>一个以陪伴为主页的健康支持空间。<br />你可以不用说真实姓名。</p>
          <div className="grow" />
          <span className="privacy-pill"><Icon name="lock" size={14} /> 匿名模式 · 默认开启</span>
          <Button full onClick={() => setStep(1)}>匿名进入 U2</Button>
          <small><Icon name="shield" size={13} /> 不收集姓名、号码或住址</small>
        </div>
      )}
      {step === 1 && (
        <div className="onboarding-body enter">
          <h1>在这里，<br />你可以不用说真实姓名。</h1>
          <div className="stack">
            {[
              ['lock', '无需注册、无需手机号', '不收集姓名、身份证或住址'],
              ['shield', '记录默认只存在你的设备', '不自动上传聊天或健康数据'],
              ['eyeoff', '随时一键隐藏', '需要时立刻切换到普通备忘录'],
            ].map(([icon, title, text]) => (
              <div className="promise" key={title}>
                <span><Icon name={icon as IconName} /></span>
                <div><strong>{title}</strong><small>{text}</small></div>
              </div>
            ))}
          </div>
          <div className="grow" />
          <Button full onClick={() => setStep(2)}>我明白了</Button>
        </div>
      )}
      {step === 2 && (
        <div className="onboarding-body enter">
          <h1>现在的你，更接近哪一种？</h1>
          <p>这只是帮助 U2 调整内容，随时可以修改。</p>
          <div className="stack">
            {statusOptions.map((option) => (
              <button key={option.value} className={`choice-card ${status === option.value ? 'active' : ''}`} onClick={() => setStatus(option.value)}>
                <span><Icon name={option.icon} /></span>
                <div className="grow"><strong>{option.title}</strong><small>{option.text}</small></div>
                <i>{status === option.value && <Icon name="check" size={13} />}</i>
              </button>
            ))}
          </div>
          <div className="grow" />
          <Button full disabled={!status} onClick={() => setStep(3)}>继续</Button>
        </div>
      )}
      {step === 3 && (
        <div className="onboarding-body enter">
          <h1>你来决定怎么保存</h1>
          <p>这些都可以随时在设置里更改。</p>
          <div className="card stack">
            <Toggle title="在本机保存记录" text="健康、情绪与偏好保存在本设备" value={saveLocal} setValue={setSaveLocal} />
            <Toggle title="保存聊天记录" text="关闭后原始消息和摘要都不会落盘" value={saveChat} setValue={setSaveChat} />
            <Toggle title="开启一键隐藏" text="随时切换到普通备忘录界面" value={hideEnabled} setValue={setHideEnabled} />
            <Toggle title="下载本地 AI 模型" text="Gemma 4 在设备上运行，对话全程不联网；需要 2–4 GB 存储" value={modelConsent} setValue={setModelConsent} />
          </div>
          <Notice>{modelConsent ? 'AI 模型将在进入 App 后立即开始后台下载，下载期间全部功能可正常使用。' : '不下载模型时，U2 将使用内置安全模板回复，量表、记录、风险评估等功能不受影响。'}</Notice>
          <div className="grow" />
          <Button full onClick={() => void finish()}>进入 U2</Button>
        </div>
      )}
    </div>
  )
}

function Toggle({ title, text, value, setValue }: { title: string; text: string; value: boolean; setValue: (value: boolean) => void }) {
  return (
    <div className="toggle-row">
      <div className="grow"><strong>{title}</strong><small>{text}</small></div>
      <button aria-label={title} className={`switch ${value ? 'active' : ''}`} onClick={() => setValue(!value)} />
    </div>
  )
}
