import { Mission, MissionStatus } from '@/types';

export const MVP_MISSION: Mission = {
  id: 'community-activity-drop',
  careerId: 'data-analyst',
  title: '分析社区论坛用户活跃度下降原因',
  description: '用数据分析方法定位社区论坛最近两周用户活跃度下降的原因，并给出可执行建议。',
  background:
    '社区论坛最近两周日活用户从平均 1200 人下降到 850 人左右。运营团队需要判断问题来自内容供给、老用户流失，还是功能体验变化。',
  objectives: ['分析活跃度时间趋势', '对比新老用户活跃变化', '拆解关键互动行为', '提出下一步验证和改进建议'],
  deliverables: ['Markdown 分析报告', '数据口径说明', '趋势图或对比图说明', '可执行改进建议'],
  criteria: ['是否能拆解业务问题', '是否说明数据口径', '是否形成证据链', '建议是否可执行'],
  difficulty: 'medium',
  status: MissionStatus.AVAILABLE,
  rewardExp: 120,
  rewardSkills: ['数据清洗', '指标分析', '可视化表达', '业务洞察'],
};
