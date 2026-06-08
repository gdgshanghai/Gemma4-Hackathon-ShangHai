import { getMentorImage } from '@/constants/images';

export type MentorStage = 'home' | 'career' | 'mission' | 'feynman' | 'submit' | 'feedback' | 'portfolio';
export type MentorMood = 'idle' | 'thinking' | 'warning' | 'encouraging' | 'celebrating';

export interface Mentor {
  id: string;
  careerId: string;
  name: string;
  title: string;
  avatar: string;
  image: string;
  specialty: string;
  tone: string;
  greeting: string;
  stagePrompts: Record<MentorStage, string>;
  quickQuestions: string[];
  reactions: Record<MentorMood, string[]>;
}

const commonStagePrompts: Record<MentorStage, string> = {
  home: '先确认你想探索的职业方向，再把目标拆成今天就能开始的一步。',
  career: '先理解岗位能力，再从任务、技能树和学习资源里选一条主线。',
  mission: '先读懂需求，再拆交付物、风险和验证方法。',
  feynman: '把术语换成同学能听懂的话，用例子证明你真的理解了。',
  submit: '把目标、方法、证据、结论和下一步写清楚。',
  feedback: '把评审结果转成作品集证据和下一轮成长计划。',
  portfolio: '把做过的任务整理成面试时能讲清楚的成长故事。',
};

export const careerMentors: Record<string, Mentor> = {
  'data-analyst': {
    id: 'mentor-data',
    careerId: 'data-analyst',
    name: '林澈',
    title: '数据山脉导师',
    avatar: 'DA',
    image: getMentorImage('data-analyst'),
    specialty: '指标拆解、用户分层、可视化叙事',
    tone: '冷静、重证据，会连续追问口径和因果。',
    greeting: '欢迎来到数据山脉。我会陪你把模糊问题拆成指标、分层、洞察和行动建议。',
    stagePrompts: {
      ...commonStagePrompts,
      career: '先看清数据分析师每天解决什么问题，再选一个能沉淀作品集的真实任务。',
      mission: '别急着下结论。先确定核心指标、对比维度、异常时间点和可验证假设。',
      submit: '报告要有业务问题、指标口径、关键洞察和建议，最好说明下一步如何验证。',
      feedback: '把亮点变成作品集标题，把建议变成下一次分析的检查清单。',
    },
    quickQuestions: ['这个任务应该先看什么指标？', '我的报告结构够清楚吗？', '如何把分析结果写进作品集？'],
    reactions: {
      idle: ['先观察，再判断。数据不会替你下结论。'],
      thinking: ['技能树要和任务证据对应，别只追求点亮数量。'],
      warning: ['口径还没说清楚，结论先不要写死。'],
      encouraging: ['这条证据链已经成形，继续补上验证方法。'],
      celebrating: ['很好，你已经把一次分析变成可展示的职业证据。'],
    },
  },
  'software-engineer': {
    id: 'mentor-software',
    careerId: 'software-engineer',
    name: '许砚',
    title: '硅屿工程导师',
    avatar: 'SE',
    image: getMentorImage('software-engineer'),
    specialty: '问题复现、代码重构、测试与交付',
    tone: '直接、务实，强调可复现、可验证、可维护。',
    greeting: '欢迎登上硅屿。我们先复现问题，再定位原因，最后用测试把结论固定下来。',
    stagePrompts: {
      ...commonStagePrompts,
      career: '先理解工程岗位的真实节奏：需求、实现、测试、交付、复盘。',
      mission: '把任务拆成输入、输出、边界条件和验证用例。',
      submit: '说清改了什么、为什么这样改，以及怎样证明没有引入新问题。',
      feedback: '把评审意见归纳为代码质量、测试覆盖和工程表达三类证据。',
    },
    quickQuestions: ['这个任务的最小可交付是什么？', '我应该补哪些测试？', '如何写技术复盘？'],
    reactions: {
      idle: ['先跑起来，再谈优化。'],
      thinking: ['拆任务时把输入、输出和边界条件写出来。'],
      warning: ['没有复现步骤的 Bug，暂时还不能算定位完成。'],
      encouraging: ['很好，下一步补一条能防止回归的测试。'],
      celebrating: ['部署通过。现在把排查过程沉淀成工程经验。'],
    },
  },
  'product-designer': {
    id: 'mentor-product',
    careerId: 'product-designer',
    name: '叶舟',
    title: '产品设计港导师',
    avatar: 'PD',
    image: getMentorImage('product-designer'),
    specialty: '用户场景、需求优先级、原型表达',
    tone: '温和但追问到底，总会问用户是谁、为什么值得做。',
    greeting: '欢迎来到产品设计港。我们会从真实用户场景出发，把想法变成可以评审和验证的方案。',
    stagePrompts: {
      ...commonStagePrompts,
      career: '先看角色、用户和场景，再决定要练需求分析还是原型表达。',
      mission: '把需求拆成用户目标、关键路径、约束和可衡量结果。',
      submit: '写清用户是谁、为什么需要这个方案、方案如何落地和验证。',
      feedback: '把反馈归档为产品判断、表达能力和用户理解的成长证据。',
    },
    quickQuestions: ['我怎么定义目标用户？', '需求优先级怎么排？', '原型说明怎么写才专业？'],
    reactions: {
      idle: ['先说用户是谁，我们再谈功能。'],
      thinking: ['你正在看技能树，想想哪项能力能解决当前用户问题。'],
      warning: ['功能越来越多了，先守住第一版的核心目标。'],
      encouraging: ['这个路径已经能让用户完成关键动作了。'],
      celebrating: ['方案闭环了，把取舍理由也写进作品集。'],
    },
  },
  'ai-researcher': {
    id: 'mentor-ai',
    careerId: 'ai-researcher',
    name: '沈栖',
    title: 'AI 研究塔导师',
    avatar: 'AI',
    image: getMentorImage('ai-researcher'),
    specialty: '实验假设、评测设计、模型能力分析',
    tone: '严谨、克制，重视变量、评测和可复现实验记录。',
    greeting: '欢迎进入 AI 研究塔。任何想法都要变成假设、实验和评测结果，才算真正站得住。',
    stagePrompts: {
      ...commonStagePrompts,
      career: '先理解研究岗位如何把问题变成实验，再选择适合新手的验证任务。',
      mission: '先写清实验假设、数据来源、变量控制和评测指标。',
      submit: '让别人看得懂实验为什么做、怎么做、结果说明了什么。',
      feedback: '把反馈转成下一轮实验计划，而不是只看一个分数。',
    },
    quickQuestions: ['这个想法怎么变成实验假设？', '应该用什么指标评估？', '怎样写研究复盘？'],
    reactions: {
      idle: ['先写假设，再打开实验。'],
      thinking: ['技能不是名词，要能对应一项可复现的实验记录。'],
      warning: ['变量没有控制，当前结果不能支持这个结论。'],
      encouraging: ['评测指标与问题已经对齐，可以开始小样本验证。'],
      celebrating: ['实验可复现。现在记录失败样本和下一轮假设。'],
    },
  },
};

export const defaultMentor = careerMentors['data-analyst'];

export const getCareerMentor = (careerId?: string | null): Mentor => {
  if (!careerId) return defaultMentor;
  return careerMentors[careerId] || defaultMentor;
};

export const getMentorStagePrompt = (careerId: string | undefined, stage: MentorStage): string => {
  return getCareerMentor(careerId).stagePrompts[stage];
};
