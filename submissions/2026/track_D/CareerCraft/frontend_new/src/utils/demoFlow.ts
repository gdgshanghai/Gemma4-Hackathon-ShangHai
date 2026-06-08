import { ROUTES } from '@/constants';

export const MVP_MISSION_ID = 'community-activity-drop';

export const DEMO_STEPS = [
  { id: 1, shortLabel: '入岛', fullLabel: '进入数据山脉', description: '选择数据分析职业岛，开始面向计算机系大学生的职业模拟主线。' },
  { id: 2, shortLabel: '任务', fullLabel: '查看主管任务', description: '阅读 AI 主管分配的第一张真实职业任务卡。' },
  { id: 3, shortLabel: '资料', fullLabel: '寻找学习资源', description: '打开 RAG 资料馆，为任务准备教程、案例和模板。' },
  { id: 4, shortLabel: '费曼', fullLabel: '完成费曼挑战', description: '用自己的话解释核心概念，确认不是机械照抄。' },
  { id: 5, shortLabel: '接受', fullLabel: '接受任务', description: '确认交付物和评审标准，进入任务提交阶段。' },
  { id: 6, shortLabel: '提交', fullLabel: '提交分析报告', description: '提交职业草图和分析成果，交给 AI 同事评审。' },
  { id: 7, shortLabel: '评审', fullLabel: '查看 AI 评审', description: '查看导师反馈、经验值和技能成长建议。' },
  { id: 8, shortLabel: '成长', fullLabel: '沉淀作品集', description: '把完成记录沉淀进成长档案馆，形成可展示作品。' },
];

export function isDemoMode(searchParams: URLSearchParams): boolean {
  return searchParams.get('demo') === '1';
}

export function getDemoStep(searchParams: URLSearchParams): number {
  const parsed = Number.parseInt(searchParams.get('step') || '1', 10);
  return Number.isFinite(parsed) ? parsed : 1;
}

export function getNextDemoUrl(currentStep: number, missionId: string = MVP_MISSION_ID): string {
  switch (currentStep) {
    case 1:
      return `/mission/${missionId}?demo=1&step=2`;
    case 2:
      return `/mission/${missionId}?demo=1&step=3`;
    case 3:
      return `/feynman/${missionId}?demo=1&step=4`;
    case 4:
      return `/mission/${missionId}?demo=1&step=5`;
    case 5:
      return `/mission/${missionId}/submit?demo=1&step=6`;
    case 6:
      return `/mission/${missionId}/feedback?demo=1&step=7`;
    case 7:
      return `${ROUTES.PORTFOLIO}?demo=1&step=8`;
    case 8:
      return '/lobby?demo=1';
    default:
      return '/career/data-analyst?demo=1&step=1';
  }
}

export const MVP_MOCK_REPORT = `# 社区论坛用户活跃度下降分析报告

## 1. 任务背景
社区论坛最近两周日活用户出现明显下降。运营团队希望判断问题来自内容供给、老用户流失，还是功能体验变化，并给出下一步验证建议。

## 2. 分析口径
- DAU：当天有发帖、评论、点赞等互动行为的独立用户。
- 新用户：注册时间不满 7 天的用户。
- 老用户：注册时间大于等于 7 天的用户。
- 观察周期：最近 14 天。

## 3. 初步发现
- 日活下降主要发生在第 8 天之后，下降幅度约为 30%。
- 新用户数量基本稳定，主要波动来自老用户活跃下降。
- 发帖量下降明显，评论和点赞下降相对较小。
- 这说明问题可能不是获客不足，而是老用户缺少继续发帖的动力。

## 4. 结论
社区活跃度下降的主要原因可能是老用户流失和发帖动力不足。当前更应该优先分析老用户最近一次发帖后的反馈情况，以及是否存在产品改版或内容推荐变化。

## 5. 建议
1. 对流失老用户做访谈，确认是否与内容质量或功能体验有关。
2. 统计发帖后的评论反馈率，判断创作者是否缺少正反馈。
3. 设计老用户召回活动，并设置 7 天留存和发帖转化作为验证指标。
4. 在下一个版本中优化发帖入口和内容推荐机制。`;

export const MVP_RAG_RESOURCES = [
  {
    id: 1,
    title: 'Pandas 分组聚合入门',
    category: '教程',
    description: '学习使用 groupby 做用户分层和行为统计。',
  },
  {
    id: 2,
    title: 'Matplotlib 趋势图绘制',
    category: '教程',
    description: '用 Python 绘制时间趋势和对比图。',
  },
  {
    id: 3,
    title: '活跃用户指标分析模板',
    category: '模板',
    description: '常用 DAU、留存、转化指标分析框架。',
  },
  {
    id: 4,
    title: '用户留存与活跃度分析案例',
    category: '案例',
    description: '真实项目中用户分析的完整案例。',
  },
];
