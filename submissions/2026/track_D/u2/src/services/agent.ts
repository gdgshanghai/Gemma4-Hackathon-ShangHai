import type { AgentReply, ChatMessage, TrustEvidence, TrustLevel } from '../types'
import { retrieveKnowledge } from '../content/knowledge'
import { localAI } from './localAI'

const crisisKeywords = ['不想活', '自杀', '结束生命', '活不下去', '伤害自己', '割腕', '跳楼']

export function hasCrisisSignal(text: string) {
  return crisisKeywords.some((keyword) => text.includes(keyword))
}

export function buildSystemPrompt(trust: TrustLevel, evidence: TrustEvidence[], context: string) {
  return `你是 U2，一位温暖、克制、不评判的 HIV 健康支持伙伴。
医疗安全边界：不做确诊或排除诊断；不输出感染概率；不提供个体药物、停药或换药建议；紧急暴露优先引导 72 小时内就医评估；危机优先 12356/110/120。
当前医院信任状态：${trust}。近期证据仅用于调整解释方式，不把它描述成用户标签：${evidence.slice(-4).map((item) => item.quote).join('、') || '无'}。
使用简洁中文回答，先共情，再给 1 至 3 个可执行步骤。可引用以下本地资料：
${context || '本轮无直接匹配资料。'}`
}

export function buildModelMessages(
  text: string,
  history: ChatMessage[],
  trust: TrustLevel,
  evidence: TrustEvidence[],
) {
  const citations = retrieveKnowledge(text)
  const context = citations.map((item) => `${item.title}：${item.content}（来源：${item.source}）`).join('\n')
  return {
    citations,
    messages: [
      { role: 'system' as const, content: buildSystemPrompt(trust, evidence, context) },
      ...history.slice(-8).map((item) => ({ role: item.role, content: item.content } as const)),
      { role: 'user' as const, content: text },
    ],
  }
}

function safeFallback(text: string, trust: TrustLevel): AgentReply {
  const citations = retrieveKnowledge(text)
  if (/pep|阻断|暴露|高危/i.test(text)) {
    return { content: '我能感觉到你现在很着急。是否需要 PEP 必须结合暴露方式和时间由专业人员评估；如果仍在 72 小时内，请优先联系感染科、急诊或当地疾控，越早评估越好。这里不会根据几句话判断你是否感染。', crisis: false, tool: 'risk', citations }
  }
  if (/cd4|病毒载量|病载|报告/i.test(text)) {
    return { content: '我可以帮你整理指标含义和复诊问题。单次数值不能独立判断治疗效果，也不要据此自行停药或换药。你可以把报告录入健康页，我们一起看趋势。', crisis: false, tool: 'none', citations }
  }
  if (/u=u|传染|传播/i.test(text)) {
    return { content: 'U=U 的核心是：坚持规范治疗并持续保持病毒载量检测不到时，不会通过性行为传播 HIV。它不等于治愈，规律服药和复查仍然重要。', crisis: false, tool: 'u-equals-u', citations }
  }
  if (/焦虑|害怕|恐艾|睡不着|崩溃|难过/i.test(text)) {
    return { content: '谢谢你把这份不安说出来。我们先不急着下结论：你现在最难受的是身体上的担心，还是脑子里停不下来的反复想象？如果愿意，我们可以只处理眼前最压人的那一小块。', crisis: false, tool: 'assessment', citations }
  }
  const bridge = trust === 'hesitant'
    ? '我不会逼你相信某个结论。我们可以先把你不信任的具体原因和可验证的信息分开。'
    : '我会陪你把信息理清，但不会替代医生做诊断。'
  return { content: `${bridge} 你现在最希望先解决哪件事：情绪、风险判断、报告理解，还是日常治疗管理？`, crisis: false, tool: 'none', citations }
}

export async function runAgent(
  text: string,
  history: ChatMessage[],
  trust: TrustLevel,
  evidence: TrustEvidence[],
  onChunk?: (text: string) => void,
): Promise<AgentReply> {
  if (hasCrisisSignal(text)) {
    return {
      content: '我很在意你此刻的安全。请先不要独自行动，尽量去到有人的地方，并联系一个可信任的人陪着你。你可以立即拨打全国心理援助热线 12356；如果已经有明确计划、工具或无法保证安全，请立刻拨打 110 或 120。',
      crisis: true,
      tool: 'none',
    }
  }
  const fallback = safeFallback(text, trust)
  if (localAI.state().status !== 'ready') return fallback
  const modelInput = buildModelMessages(text, history, trust, evidence)
  try {
    const content = await localAI.generate({
      messages: modelInput.messages,
      onChunk,
    })
    return { ...fallback, citations: modelInput.citations, content: content.trim() || fallback.content }
  } catch {
    return fallback
  }
}
