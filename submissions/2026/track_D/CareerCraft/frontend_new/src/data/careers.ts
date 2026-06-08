import { CareerIsland } from '@/types';

export const careerIslands: CareerIsland[] = [
  {
    id: 'data-analyst',
    name: '数据分析山脉',
    islandName: 'Isle of Insight',
    description: '从用户行为、业务指标和实验数据中寻找线索，训练把问题讲清楚的能力。',
    mentorName: '数据导师',
    mentorAvatar: 'DA',
    themeColor: '#f59e0b',
    careers: [
      {
        id: 'junior-data-analyst',
        name: '初级数据分析师',
        description: '学习指标口径、分组分析、可视化和业务建议表达。',
        icon: 'DA',
        color: '#f59e0b',
        unlocked: true,
      },
    ],
  },
  {
    id: 'software-engineer',
    name: '硅之岛',
    islandName: 'Silicon Isle',
    description: '在代码、测试和系统设计中完成真实工程任务，训练可交付的工程思维。',
    mentorName: '工程导师',
    mentorAvatar: 'SE',
    themeColor: '#38bdf8',
    careers: [
      {
        id: 'junior-software-engineer',
        name: '初级软件工程师',
        description: '学习问题复现、代码修复、测试覆盖和技术复盘。',
        icon: 'SE',
        color: '#38bdf8',
        unlocked: true,
      },
    ],
  },
  {
    id: 'product-designer',
    name: '产品设计港',
    islandName: 'Product Design Harbor',
    description: '把用户需求、交互原型和产品判断串成一条路线，训练从想法到方案的表达。',
    mentorName: '产品导师',
    mentorAvatar: 'PM',
    themeColor: '#fb7185',
    careers: [
      {
        id: 'product-manager-trainee',
        name: '产品经理实训生',
        description: '学习需求拆解、用户旅程、原型说明和优先级判断。',
        icon: 'PM',
        color: '#fb7185',
        unlocked: true,
      },
    ],
  },
  {
    id: 'ai-researcher',
    name: 'AI 研究塔',
    islandName: 'AI Research Tower',
    description: '从模型能力、数据集和评测实验出发，训练把 AI 想法变成可验证方案的能力。',
    mentorName: '研究导师',
    mentorAvatar: 'AI',
    themeColor: '#a78bfa',
    careers: [
      {
        id: 'ai-research-intern',
        name: 'AI 研究实习生',
        description: '学习实验设计、提示工程、模型评估和研究复盘。',
        icon: 'AI',
        color: '#a78bfa',
        unlocked: false,
      },
    ],
  },
];
