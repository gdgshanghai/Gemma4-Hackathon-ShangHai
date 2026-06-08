import type { AssessmentKind } from '../types'

export const ASSESSMENTS = {
  'GAD-7': {
    description: '过去两周内 · 焦虑自评',
    questions: ['感到紧张、焦虑或烦躁', '无法停止或控制担忧', '对各种事情担忧过多', '很难放松下来', '心神不宁，难以静坐', '变得容易烦恼或易怒', '感到害怕，好像有可怕的事会发生'],
  },
  'PHQ-9': {
    description: '过去两周内 · 抑郁筛查',
    questions: ['做事时提不起劲或没有兴趣', '感到心情低落、沮丧或绝望', '入睡困难、睡不安稳或睡眠过多', '感到疲倦或没有活力', '食欲不振或吃太多', '觉得自己很糟，或让家人失望', '注意力难以集中', '行动或说话明显变慢，或坐立不安', '有不如死掉或伤害自己的念头'],
  },
} satisfies Record<AssessmentKind, { description: string; questions: string[] }>

export const ASSESSMENT_OPTIONS = ['完全不会', '好几天', '一半以上的天数', '几乎每天']

export function scoreAssessment(kind: AssessmentKind, answers: number[]) {
  const score = answers.reduce((sum, value) => sum + value, 0)
  const levels = kind === 'PHQ-9'
    ? [[4, '最小'], [9, '轻度'], [14, '中度'], [19, '中重度'], [27, '重度']] as const
    : [[4, '最小'], [9, '轻度'], [14, '中度'], [21, '重度']] as const
  const level = levels.find(([max]) => score <= max)?.[1] ?? '重度'
  return { score, level, selfHarmRisk: kind === 'PHQ-9' && (answers[8] ?? 0) > 0 }
}
