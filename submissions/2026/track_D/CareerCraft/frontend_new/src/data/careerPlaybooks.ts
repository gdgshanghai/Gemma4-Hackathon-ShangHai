import { Mission, MissionStatus } from '@/types';

export interface CareerRoadmapStage {
  name: string;
  description: string;
  reward: string;
  practice: string;
}

export interface CareerPlaybook {
  careerId: string;
  premise: string;
  roadmaps: CareerRoadmapStage[];
  bridgeMissions: Mission[];
}

const available = MissionStatus.AVAILABLE;
const locked = MissionStatus.LOCKED;

export const careerPlaybooks: Record<string, CareerPlaybook> = {
  'software-engineer': {
    careerId: 'software-engineer',
    premise: '软件工程不是只学语法，而是把问题复现、实现、验证和复盘连接成稳定交付。',
    roadmaps: [
      { name: '复现问题', description: '把模糊反馈变成稳定复现步骤。', reward: '问题修复者', practice: '记录输入、输出、环境和错误信息。' },
      { name: '测试守门', description: '覆盖正常、异常和边界路径。', reward: '测试守门员', practice: '为一次修复补三条关键用例。' },
      { name: '接口协作', description: '讲清需求、接口、校验和错误处理。', reward: '协作工程师', practice: '写一份接口说明和验收清单。' },
      { name: '交付复盘', description: '从日志、指标和代码结构定位长期问题。', reward: '交付负责人', practice: '沉淀一份技术复盘。' },
    ],
    bridgeMissions: [
      {
        id: 'se-api-debug-brief',
        careerId: 'software-engineer',
        title: '接口鉴权故障排查',
        description: '复现本地与评审环境的接口差异，并提交可验证的修复说明。',
        background: '一个在本地正常的接口在评审环境返回 401。你需要比较请求信息、定位根因并补充回归测试。',
        objectives: ['记录复现步骤', '比较环境差异', '定位根因', '补充回归测试'],
        deliverables: ['排查记录', '修复说明', '测试清单'],
        criteria: ['步骤可复现', '根因有证据', '测试覆盖关键路径'],
        difficulty: 'easy',
        status: available,
        rewardExp: 180,
        rewardSkills: ['问题复现', '接口调试', '测试设计'],
      },
      {
        id: 'se-observability-review',
        careerId: 'software-engineer',
        title: '服务异常日志复盘',
        description: '从日志和指标中还原一次服务异常，并提出可落地的监控改进。',
        background: '服务偶发超时但缺少统一记录。你需要设计排查顺序，并说明下一次如何更快发现问题。',
        objectives: ['整理时间线', '分析关键日志', '识别监控缺口', '提出改进方案'],
        deliverables: ['异常时间线', '证据清单', '监控改进方案'],
        criteria: ['证据可追溯', '推断边界清楚', '改进方案可执行'],
        difficulty: 'medium',
        status: locked,
        rewardExp: 260,
        rewardSkills: ['日志分析', '可观测性', '工程复盘'],
      },
    ],
  },
  'data-analyst': {
    careerId: 'data-analyst',
    premise: '数据分析不是画图，而是把业务问题、指标口径、证据链和行动建议串起来。',
    roadmaps: [
      { name: '定义口径', description: '把问题翻译成可计算指标。', reward: '数据侦察员', practice: '写清公式、时间范围和分层方式。' },
      { name: '拆解异常', description: '从趋势、分组和行为差异定位原因。', reward: '洞察记录员', practice: '至少比较两个用户分层。' },
      { name: '讲清结论', description: '用图表和文字让业务方看懂证据。', reward: '报告锻造师', practice: '每个结论绑定一条证据。' },
      { name: '验证建议', description: '把建议变成下一步实验或运营动作。', reward: '业务顾问', practice: '写出验证指标和预期结果。' },
    ],
    bridgeMissions: [
      {
        id: 'da-retention-diagnosis',
        careerId: 'data-analyst',
        title: '新老用户活跃下降诊断',
        description: '拆解活跃度下降来自获客、激活还是留存，并提出验证方案。',
        background: '产品 DAU 连续两周下降。团队需要判断主要问题发生在哪类用户和哪个行为环节。',
        objectives: ['定义活跃口径', '设计用户分层', '定位异常环节', '提出验证动作'],
        deliverables: ['指标口径表', '分层分析', '洞察摘要', '验证建议'],
        criteria: ['口径一致', '分层合理', '结论有证据', '建议可验证'],
        difficulty: 'medium',
        status: available,
        rewardExp: 220,
        rewardSkills: ['指标体系', '用户分层', '分析表达'],
      },
    ],
  },
  'product-designer': {
    careerId: 'product-designer',
    premise: '产品能力来自真实取舍：用户是谁、问题是什么、为什么现在做、第一版做到哪里。',
    roadmaps: [
      { name: '用户场景', description: '识别目标用户和真实使用场景。', reward: '需求观察员', practice: '写出用户、目标、痛点和约束。' },
      { name: '需求切片', description: '把大需求切成可交付第一版。', reward: 'MVP 切片师', practice: '列出必须做、暂缓做和不做。' },
      { name: '方案表达', description: '用用户旅程和原型讲清方案。', reward: '原型讲述者', practice: '让同学按说明走完关键路径。' },
      { name: '验证闭环', description: '定义指标判断方案是否有效。', reward: '产品实训生', practice: '为方案写两个成功指标。' },
    ],
    bridgeMissions: [
      {
        id: 'pm-learning-community-mvp',
        careerId: 'product-designer',
        title: '学习社区第一版需求切片',
        description: '把学习社区改版切成一个可交付、可验证的 MVP 方案。',
        background: '团队想同时做帖子流、私信和积分。你需要聚焦一个新手用户目标，明确第一版边界。',
        objectives: ['定义目标用户', '拆解核心场景', '确定 MVP 范围', '设计验证指标'],
        deliverables: ['需求切片说明', '用户旅程草图', '功能清单', '验证指标'],
        criteria: ['用户目标清晰', '范围取舍合理', '方案能被实现', '指标可验证'],
        difficulty: 'easy',
        status: available,
        rewardExp: 180,
        rewardSkills: ['需求拆解', '用户旅程', '优先级判断'],
      },
      {
        id: 'pm-engineer-mailbox',
        careerId: 'product-designer',
        title: '工程师信箱体验优化',
        description: '设计从提问、社区讨论到问题关闭的完整人工协助流程。',
        background: '学习者遇到环境和经验问题时，需要从 AI 辅助转向人工社区。你要让路径清晰、可信且低成本。',
        objectives: ['梳理提问路径', '定义问题状态', '设计讨论结构', '明确关闭标准'],
        deliverables: ['流程说明', '状态定义', '页面结构', '体验风险清单'],
        criteria: ['流程不混乱', '状态清楚', '能减少无效提问', '能沉淀社区经验'],
        difficulty: 'medium',
        status: available,
        rewardExp: 240,
        rewardSkills: ['服务流程', '信息架构', '社区产品'],
      },
    ],
  },
  'ai-researcher': {
    careerId: 'ai-researcher',
    premise: 'AI 研究不是追模型名，而是把想法变成假设、变量、评测和可复现记录。',
    roadmaps: [
      { name: '提出假设', description: '把灵感写成可验证问题。', reward: '假设记录员', practice: '写清变量、对象和预期变化。' },
      { name: '设计评测', description: '选择能回答问题的指标和样本。', reward: '评测设计师', practice: '说明为什么指标合适。' },
      { name: '运行实验', description: '记录配置、结果和失败样本。', reward: '实验执行者', practice: '保留可复现实验日志。' },
      { name: '研究复盘', description: '讲清结论和下一轮计划。', reward: '研究实习生', practice: '写出结果解释和下一轮实验。' },
    ],
    bridgeMissions: [
      {
        id: 'ai-prompt-eval-lab',
        careerId: 'ai-researcher',
        title: '任务生成提示词评测',
        description: '比较两版提示词的任务生成质量，并完成小样本实验复盘。',
        background: '团队想确认新提示词能否让大学生更容易理解和执行职业任务。',
        objectives: ['提出实验假设', '准备评测样本', '制定评分维度', '记录失败案例'],
        deliverables: ['实验设计', '评分表', '结果摘要', '改进建议'],
        criteria: ['假设清楚', '指标能解释结果', '记录可复现', '复盘有下一步'],
        difficulty: 'medium',
        status: available,
        rewardExp: 240,
        rewardSkills: ['实验设计', '模型评测', '研究复盘'],
      },
      {
        id: 'ai-rag-grounding',
        careerId: 'ai-researcher',
        title: 'RAG 引用可靠性评测',
        description: '评估知识库回答是否真正引用了相关职业资料。',
        background: '知识档案库能返回资料，但团队担心答案与来源脱节。你需要设计一套小规模可靠性评测。',
        objectives: ['定义相关性标准', '准备评测问题', '核对引用依据', '分析失败模式'],
        deliverables: ['评测集', '评分规则', '结果报告', '改进建议'],
        criteria: ['标准清晰', '样本覆盖典型场景', '评分可复核', '建议能落地'],
        difficulty: 'hard',
        status: locked,
        rewardExp: 320,
        rewardSkills: ['RAG 评测', '引用核验', '研究报告'],
      },
    ],
  },
};

export function getCareerPlaybook(careerId: string): CareerPlaybook {
  return careerPlaybooks[careerId] || careerPlaybooks['software-engineer'];
}

export function mergeCareerMissions(careerId: string, baseMissions: Mission[]): Mission[] {
  const playbook = getCareerPlaybook(careerId);
  const existingIds = new Set(baseMissions.map((mission) => mission.id));
  return [...baseMissions, ...playbook.bridgeMissions.filter((mission) => !existingIds.has(mission.id))];
}
