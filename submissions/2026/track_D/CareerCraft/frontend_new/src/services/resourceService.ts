import { resources } from '@/data';
import { Resource } from '@/types';
import { api, Resource as BackendResource } from './apiClient';
import { resourceDomainForCareer } from './apiAdapters';

function queryForCareer(careerId: string) {
  if (careerId.includes('software')) return '代码调试 单元测试 API 设计';
  if (careerId.includes('product')) return '需求拆解 用户旅程 原型 产品方案';
  if (careerId.includes('ai') || careerId.includes('research')) return '模型评估 提示工程 实验设计';
  return '数据分析 数据清洗 用户活跃度';
}

function mapBackendResources(items: BackendResource[], type: string): Resource[] {
  return items.map((item) => ({
    id: item.doc_id,
    title: item.title,
    type,
    summary: item.snippet,
    relevance: Math.round(item.relevance_score * 100),
    tags: item.tags || (item.source ? [item.source] : []),
  }));
}

export const resourceService = {
  getResourcesByCareerId: async (careerId: string): Promise<Resource[]> => {
    try {
      const result = await api.searchKnowledgeBase(queryForCareer(careerId), resourceDomainForCareer(careerId));
      const backendResources = mapBackendResources(result, '知识库');
      const fallback = resources[careerId] || [];
      const ids = new Set(backendResources.map((item) => item.id));
      return [...backendResources, ...fallback.filter((item) => !ids.has(item.id))];
    } catch (error) {
      console.warn('知识库接口不可用，使用本地职业资源。', error);
      return resources[careerId] || [];
    }
  },

  searchResources: async (query: string, careerId: string): Promise<Resource[]> => {
    try {
      return mapBackendResources(await api.searchKnowledgeBase(query, resourceDomainForCareer(careerId)), '检索结果');
    } catch (error) {
      console.warn('RAG 检索失败，使用本地职业资源。', error);
      return resources[careerId] || [];
    }
  },
};
