import { CareerIsland, Mission, SkillNode, Resource } from '@/types';
import { MissionStatus } from '@/types';

export const mockCareerIslands: CareerIsland[] = [
  {
    id: 'software-engineer',
    name: '软件工程岛',
    islandName: 'Silicon Isle',
    description: '踏入代码的世界，构建未来的数字王国！',
    mentorName: '代码导师',
    mentorAvatar: '👨‍💻',
    themeColor: '#3b82f6',
    careers: []
  },
  {
    id: 'data-analyst',
    name: '数据分析山脉',
    islandName: 'Isle of Insight',
    description: '攀登数据的高峰，从数字中发现价值！',
    mentorName: '数据导师',
    mentorAvatar: '👩‍🔬',
    themeColor: '#8b5cf6',
    careers: []
  }
];

export const mockSkillTrees = {
  'software-engineer': [
    { 
      id: 'se-debug', 
      name: '代码调试', 
      description: '定位和修复代码中的问题', 
      level: 1, 
      maxLevel: 5, 
      exp: 80, 
      expToNext: 200, 
      unlocked: true, 
      x: 0, 
      y: 0, 
      prerequisites: [], 
      children: ['se-test'] 
    },
    { 
      id: 'se-test', 
      name: '单元测试', 
      description: '编写高质量的测试用例', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 150, 
      unlocked: true, 
      x: -1, 
      y: 1, 
      prerequisites: ['se-debug'], 
      children: ['se-api'] 
    },
    { 
      id: 'se-api', 
      name: 'API 设计', 
      description: '设计优雅的应用程序接口', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 180, 
      unlocked: false, 
      x: 0, 
      y: 1, 
      prerequisites: ['se-test'], 
      children: ['se-log'] 
    },
    { 
      id: 'se-log', 
      name: '日志分析', 
      description: '从日志中发现系统异常', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 150, 
      unlocked: false, 
      x: 1, 
      y: 1, 
      prerequisites: ['se-api'], 
      children: ['se-quality'] 
    },
    { 
      id: 'se-quality', 
      name: '代码质量', 
      description: '提高代码的可读性和可维护性', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 200, 
      unlocked: false, 
      x: 0, 
      y: 2, 
      prerequisites: ['se-log'], 
      children: ['se-comm'] 
    },
    { 
      id: 'se-comm', 
      name: '技术沟通', 
      description: '清晰表达技术概念和方案', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 180, 
      unlocked: false, 
      x: 0, 
      y: 3, 
      prerequisites: ['se-quality'], 
      children: [] 
    }
  ],
  'data-analyst': [
    { 
      id: 'da-clean', 
      name: '数据清洗', 
      description: '处理和清理原始数据', 
      level: 1, 
      maxLevel: 5, 
      exp: 100, 
      expToNext: 180, 
      unlocked: true, 
      x: 0, 
      y: 0, 
      prerequisites: [], 
      children: ['da-sql'] 
    },
    { 
      id: 'da-sql', 
      name: 'SQL 查询', 
      description: '从数据库中提取数据', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 150, 
      unlocked: true, 
      x: -1, 
      y: 1, 
      prerequisites: ['da-clean'], 
      children: ['da-desc'] 
    },
    { 
      id: 'da-desc', 
      name: '描述性分析', 
      description: '分析和描述数据特征', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 160, 
      unlocked: false, 
      x: 0, 
      y: 1, 
      prerequisites: ['da-sql'], 
      children: ['da-conv'] 
    },
    { 
      id: 'da-conv', 
      name: '转化率分析', 
      description: '分析转化漏斗和优化策略', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 200, 
      unlocked: false, 
      x: 1, 
      y: 1, 
      prerequisites: ['da-desc'], 
      children: ['da-visual'] 
    },
    { 
      id: 'da-visual', 
      name: '数据可视化', 
      description: '用图表展示数据洞察', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 180, 
      unlocked: false, 
      x: 0, 
      y: 2, 
      prerequisites: ['da-conv'], 
      children: ['da-report'] 
    },
    { 
      id: 'da-report', 
      name: '报告撰写', 
      description: '撰写专业的数据分析报告', 
      level: 0, 
      maxLevel: 5, 
      exp: 0, 
      expToNext: 170, 
      unlocked: false, 
      x: 0, 
      y: 3, 
      prerequisites: ['da-visual'], 
      children: [] 
    }
  ]
};

export const mockMissions = {
  'software-engineer': [
    {
      id: 'se-bug-hunter',
      careerId: 'software-engineer',
      title: '漏洞捕手',
      description: '定位和修复代码库中的关键 Bug',
      background: '公司生产系统出现了几个关键 Bug，用户反馈强烈。你需要定位问题并修复它们！',
      objectives: ['复现 3 个 Bug', '分析问题根因', '修复代码缺陷', '编写修复说明'],
      deliverables: ['修复后的代码', 'Bug 分析报告', '测试验证截图'],
      criteria: ['Bug 修复率 100%', '代码有注释说明', '修复后功能正常'],
      difficulty: 'easy',
      status: MissionStatus.AVAILABLE,
      rewardExp: 150,
      rewardSkills: ['se-debug']
    },
    {
      id: 'se-unit-test',
      careerId: 'software-engineer',
      title: '单测守门人',
      description: '为项目添加单元测试覆盖率',
      background: '新功能刚上线，但测试覆盖率不足 40%。你需要为核心模块添加单元测试！',
      objectives: ['编写 20 个测试用例', '使用断言验证', 'Mock 外部依赖', '测试覆盖率 80%+'],
      deliverables: ['测试代码文件', '覆盖率报告', '测试说明文档'],
      criteria: ['所有测试通过', '覆盖关键路径', '测试代码质量好'],
      difficulty: 'medium',
      status: MissionStatus.AVAILABLE,
      rewardExp: 200,
      rewardSkills: ['se-test']
    },
    {
      id: 'se-api-builder',
      careerId: 'software-engineer',
      title: 'API 铸造师',
      description: '设计和实现一组 RESTful API',
      background: '产品经理要求开发一个新的 API，用于前后端数据交互。',
      objectives: ['设计 API 文档', '实现 CRUD 接口', '添加数据验证', '错误处理机制'],
      deliverables: ['API 设计文档', '实现代码', 'API 测试结果'],
      criteria: ['API 文档清晰', '接口功能完整', '错误处理规范'],
      difficulty: 'medium',
      status: MissionStatus.LOCKED,
      rewardExp: 250,
      rewardSkills: ['se-api', 'se-quality']
    },
    {
      id: 'se-log-tracker',
      careerId: 'software-engineer',
      title: '日志追踪者',
      description: '从系统日志中定位性能问题',
      background: '系统响应变慢，需要从海量日志中找到性能瓶颈！',
      objectives: ['分析系统日志', '找到慢查询', '优化关键路径', '监控改进效果'],
      deliverables: ['日志分析报告', '性能优化方案', '前后对比数据'],
      criteria: ['问题定位准确', '优化效果明显', '方案可落地'],
      difficulty: 'hard',
      status: MissionStatus.LOCKED,
      rewardExp: 350,
      rewardSkills: ['se-log', 'se-debug']
    }
  ],
  'data-analyst': [
    {
      id: 'da-mvp-user-activity',
      careerId: 'data-analyst',
      title: '用户活跃度下降分析',
      description: '分析社区论坛用户活跃度下降原因',
      background: '社区论坛最近两周日活跃用户（DAU）出现明显下降趋势，从上周的平均 1,200 人下降到本周的 850 人，降幅约 30%。运营团队需要快速定位问题原因并给出改进建议！',
      objectives: ['分析活跃度时间趋势', '新老用户对比分析', '功能使用情况分析', '提出改进建议'],
      deliverables: ['完整分析报告', '趋势分析图表', '改进建议文档'],
      criteria: ['问题诊断准确', '分析有深度', '建议可执行'],
      difficulty: 'medium',
      status: MissionStatus.AVAILABLE,
      rewardExp: 250,
      rewardSkills: ['da-clean', 'da-sql']
    },
    {
      id: 'da-data-detective',
      careerId: 'data-analyst',
      title: '数据侦探',
      description: '清理和分析电商平台的销售数据',
      background: '市场部的数据非常杂乱，你需要从数据海洋中找到关键信息！',
      objectives: ['数据去重处理', '缺失值填充', '异常值检测', '数据格式标准化'],
      deliverables: ['清洗后的数据', '数据质量报告', '清洗脚本'],
      criteria: ['数据质量 98%+', '清洗过程可复现', '报告清晰明了'],
      difficulty: 'easy',
      status: MissionStatus.AVAILABLE,
      rewardExp: 150,
      rewardSkills: ['da-clean']
    },
    {
      id: 'da-sql-treasure',
      careerId: 'data-analyst',
      title: 'SQL 寻宝者',
      description: '用 SQL 挖掘业务数据的价值',
      background: '运营团队需要了解用户行为，你是唯一能找到数据真相的人！',
      objectives: ['多表关联查询', '分组聚合统计', '时间趋势分析', '用户画像构建'],
      deliverables: ['SQL 查询脚本', '查询结果数据集', '分析摘要'],
      criteria: ['查询效率高', '结果准确无误', '业务价值明确'],
      difficulty: 'medium',
      status: MissionStatus.AVAILABLE,
      rewardExp: 200,
      rewardSkills: ['da-sql']
    },
    {
      id: 'da-conversion-alchemist',
      careerId: 'data-analyst',
      title: '转化率炼金术',
      description: '提升产品转化漏斗的转化率',
      background: '付费转化率一直在下降，你需要分析原因并提出改进建议！',
      objectives: ['构建转化漏斗', '分析流失环节', '用户行为分析', '提出优化建议'],
      deliverables: ['漏斗分析报告', '流失用户画像', '优化方案文档'],
      criteria: ['问题诊断准确', '分析有深度', '建议可执行'],
      difficulty: 'medium',
      status: MissionStatus.LOCKED,
      rewardExp: 250,
      rewardSkills: ['da-conv', 'da-desc']
    },
    {
      id: 'da-report-forger',
      careerId: 'data-analyst',
      title: '报告锻造师',
      description: '撰写一份完整的季度业务分析报告',
      background: 'CEO 要求看一份全面的业务分析，为下季度决策做准备！',
      objectives: ['数据趋势分析', '关键指标追踪', '可视化图表', '洞察结论提炼'],
      deliverables: ['完整报告 PDF', '可视化图表包', '汇报 PPT'],
      criteria: ['结构完整清晰', '数据准确可靠', '建议有战略价值'],
      difficulty: 'hard',
      status: MissionStatus.LOCKED,
      rewardExp: 350,
      rewardSkills: ['da-report', 'da-visual']
    }
  ]
};

export const mockResources = {
  'software-engineer': [
    {
      id: 'se-res-1',
      title: '单元测试基础',
      type: '教程',
      summary: '学习如何编写高质量的单元测试，提高代码质量和稳定性',
      relevance: 95,
      tags: ['测试', '质量', '最佳实践']
    },
    {
      id: 'se-res-2',
      title: 'Bug 复现与定位方法',
      type: '指南',
      summary: '系统性的 Bug 定位方法论，从发现到修复的完整流程',
      relevance: 91,
      tags: ['调试', '问题定位', '技巧']
    },
    {
      id: 'se-res-3',
      title: 'REST API 设计指南',
      type: '规范',
      summary: 'RESTful 接口设计的最佳实践和常见规范',
      relevance: 88,
      tags: ['API', '架构', '设计模式']
    },
    {
      id: 'se-res-4',
      title: '日志排查方法论',
      type: '文档',
      summary: '如何高效地从海量日志中找到问题根因的实战经验',
      relevance: 86,
      tags: ['日志', '监控', '排查']
    }
  ],
  'data-analyst': [
    {
      id: 'da-res-1',
      title: '数据清洗入门指南',
      type: '教程',
      summary: '从零开始学习数据清洗技巧，解决数据质量问题',
      relevance: 96,
      tags: ['数据清洗', '数据质量', '预处理']
    },
    {
      id: 'da-res-2',
      title: 'SQL 聚合查询速查表',
      type: '速查表',
      summary: '常用 SQL 聚合函数和查询技巧的快速参考手册',
      relevance: 92,
      tags: ['SQL', '聚合', '查询优化']
    },
    {
      id: 'da-res-3',
      title: '转化率分析案例',
      type: '案例',
      summary: '真实业务场景下的转化率分析实践案例分享',
      relevance: 88,
      tags: ['转化率', '数据分析', '案例学习']
    },
    {
      id: 'da-res-4',
      title: '商业分析报告模板',
      type: '模板',
      summary: '专业的商业分析报告模板，让你的报告更加出色',
      relevance: 85,
      tags: ['报告', '可视化', '模板']
    }
  ]
};

export const mockMentor = {
  name: 'AI 导师',
  avatar: '🤖',
  greeting: '需要帮助吗？我可以为你推荐学习资源！'
};

export const getCareerMentor = (careerId: string) => {
  const island = mockCareerIslands.find(i => i.id === careerId);
  return {
    name: island?.mentorName || 'AI 导师',
    avatar: island?.mentorAvatar || '🤖',
    greeting: island?.id === 'software-engineer' ? 
      '你好！让我帮你成为更好的程序员！' : 
      '欢迎来到数据世界！让我们一起探索数据之美！'
  };
};

export const getRecommendResources = (careerId: string) => {
  return mockResources[careerId as keyof typeof mockResources] || [];
};
