import { Resource } from '@/types';

export const resources: Record<string, Resource[]> = {
  'software-engineer': [
    {
      id: 'se-res-1',
      title: '单元测试基础',
      type: '教程',
      summary: '学习如何编写高质量单元测试，覆盖正常路径、边界条件和异常场景。',
      relevance: 95,
      tags: ['测试', '质量', '工程实践'],
    },
    {
      id: 'se-res-2',
      title: 'Bug 复现与定位方法',
      type: '指南',
      summary: '从发现问题到修复问题的完整排查流程，适合软件工程任务演示。',
      relevance: 91,
      tags: ['调试', '问题定位', '复盘'],
    },
    {
      id: 'se-res-3',
      title: 'REST API 设计指南',
      type: '规范',
      summary: '接口设计的常见规范、命名方式、错误处理和版本管理思路。',
      relevance: 88,
      tags: ['API', '架构', '接口设计'],
    },
  ],
  'data-analyst': [
    {
      id: 'da-res-1',
      title: '数据清洗入门指南',
      type: '教程',
      summary: '从字段理解、缺失值处理到异常值排查，建立基础数据质量意识。',
      relevance: 96,
      tags: ['数据清洗', '数据质量', '预处理'],
    },
    {
      id: 'da-res-2',
      title: 'SQL 聚合查询速查',
      type: '速查表',
      summary: '常用分组、聚合、排序和窗口函数的快速参考。',
      relevance: 92,
      tags: ['SQL', '聚合', '查询优化'],
    },
    {
      id: 'da-res-3',
      title: '用户活跃度分析案例',
      type: '案例',
      summary: '把“活跃下降”拆成可验证的数据问题，并形成业务建议。',
      relevance: 90,
      tags: ['DAU', '留存', '业务分析'],
    },
    {
      id: 'da-res-4',
      title: '分析报告作品集模板',
      type: '模板',
      summary: '把任务背景、分析过程、结论和下一步建议整理成可展示成果。',
      relevance: 85,
      tags: ['报告', '作品集', '表达'],
    },
  ],
  'product-designer': [
    {
      id: 'pm-res-1',
      title: '需求拆解入门',
      type: '教程',
      summary: '从用户、场景、问题和约束四个角度拆解一个产品需求。',
      relevance: 91,
      tags: ['需求', '产品', '用户场景'],
    },
    {
      id: 'pm-res-2',
      title: '用户旅程图示例',
      type: '案例',
      summary: '学习如何把用户行为、痛点和机会点整理成一条清晰旅程。',
      relevance: 88,
      tags: ['用户旅程', '体验', '原型'],
    },
  ],
  'ai-researcher': [
    {
      id: 'ai-res-1',
      title: '实验记录与消融分析模板',
      type: '模板',
      summary: '记录模型假设、实验配置、指标变化和下一步验证方案。',
      relevance: 93,
      tags: ['实验设计', '评测', '模型分析'],
    },
    {
      id: 'ai-res-2',
      title: '模型评测指标指南',
      type: '指南',
      summary: '理解准确率、召回率、F1、AUC 等指标在不同任务中的使用边界。',
      relevance: 89,
      tags: ['评测', '指标', '机器学习'],
    },
  ],
};

export function getRecommendResources(careerId: string): Resource[] {
  return resources[careerId] || [];
}
