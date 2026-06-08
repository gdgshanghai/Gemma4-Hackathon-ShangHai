import { Feedback } from '@/types';

export const feedbacks: Record<string, Feedback> = {};

export const createMockFeedback = (missionId: string): Feedback => {
  return {
    id: `feedback-${missionId}`,
    missionId,
    score: 85,
    maxScore: 100,
    comment:
      '这次交付已经能说明你理解了任务背景，也能把分析过程和结论串起来。下一步可以补充更多证据，让建议更容易落地。',
    strengths: ['目标理解清晰', '分析逻辑完整', '报告结构适合沉淀到作品集'],
    improvements: ['补充关键指标口径', '给建议增加优先级', '说明如何验证建议是否有效'],
    skillExpGained: [
      { skillId: 'problem-framing', expGained: 10 },
      { skillId: 'business-expression', expGained: 8 },
      { skillId: 'evidence-chain', expGained: 6 },
    ],
    badgesEarned: ['数据侦察员'],
    createdAt: new Date().toISOString(),
  };
};
