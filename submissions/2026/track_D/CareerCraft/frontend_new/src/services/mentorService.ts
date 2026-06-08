import { getCareerMentor, getMentorStagePrompt, Mentor, MentorStage } from '@/data';
import { api, streamChat } from './apiClient';

export interface MentorChatContext {
  careerId?: string;
  stage?: MentorStage;
  missionTitle?: string;
  pageTopic?: string;
}

function buildRoleName(mentor: Mentor, context: MentorChatContext): string {
  const stagePrompt = getMentorStagePrompt(mentor.careerId, context.stage || 'career');
  const topic = context.missionTitle || context.pageTopic || '职业探索';
  return `${mentor.name}，${mentor.title}。专长：${mentor.specialty}。语气：${mentor.tone}。当前场景：${stagePrompt} 当前任务：${topic}`;
}

function buildMockReply(mentor: Mentor, message: string, context: MentorChatContext): string {
  const stage = context.stage || 'career';
  const topic = context.missionTitle || context.pageTopic || '当前职业探索';

  const stageAdvice: Record<MentorStage, string> = {
    home: '建议先选一个最想体验的职业岛，不要一次铺太多路线。',
    career: '先看这个职业每天解决什么问题，再挑一个能沉淀作品集的主线任务。',
    mission: '先把需求拆成目标、交付物、证据和风险，再决定是否接受任务。',
    feynman: '用一句人话解释概念，再接一个当前任务里的例子。',
    submit: '提交前检查目标、过程、证据、结论和下一步是否都写清楚。',
    feedback: '先收集亮点，再把改进建议变成下一轮任务的检查清单。',
    portfolio: '把任务结果写成“背景-行动-结果-反思”的成长故事。',
  };

  return [
    `${mentor.name}（${mentor.title}）收到你的问题：“${message}”。`,
    `结合「${topic}」，我的建议是：${stageAdvice[stage]}`,
    `再补一个 ${mentor.specialty} 视角：把你现在最不确定的点写成一个可验证的小问题，我会继续帮你往下拆。`,
  ].join('\n\n');
}

async function streamMockReply(reply: string, onChunk: (char: string) => void): Promise<string> {
  for (let i = 0; i < reply.length; i += 1) {
    onChunk(reply[i]);
    await new Promise((resolve) => window.setTimeout(resolve, 12));
  }
  return reply;
}

export const mentorService = {
  checkHealth: async (): Promise<boolean> => {
    return api.checkHealth();
  },

  getCareerMentor: async (careerId: string): Promise<Mentor> => {
    return getCareerMentor(careerId);
  },

  streamChat: async (
    message: string,
    onChunk: (char: string) => void,
    context: MentorChatContext = {},
    abortSignal?: AbortSignal
  ): Promise<string> => {
    const mentor = getCareerMentor(context.careerId);
    const roleName = buildRoleName(mentor, context);

    try {
      return await streamChat(roleName, message, onChunk, abortSignal);
    } catch {
      console.warn('AI mentor chat API unavailable, using front-end mock reply.');
      return streamMockReply(buildMockReply(mentor, message, context), onChunk);
    }
  },
};
