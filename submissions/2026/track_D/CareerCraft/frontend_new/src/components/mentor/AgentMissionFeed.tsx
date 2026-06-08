import React from 'react';
import { PixelCard, PixelBadge, PixelButton } from '@/components/pixel';
import { Resource } from '@/types';

interface AgentMissionFeedProps {
  resources: Resource[];
  careerId: string;
  onOpenRAGDrawer?: () => void;
}

const resourceRecommendations = {
  'software-engineer': [
    {
      reason: '你需要调试和修复代码问题，这个教程刚好覆盖这个场景。',
      type: '教程'
    },
    {
      reason: '单元测试能帮你确认复现路径，也防止修复后回归。',
      type: '练习'
    },
    {
      reason: '了解一些调试技巧可以让你的工作事半功倍。',
      type: '指南'
    }
  ],
  'data-analyst': [
    {
      reason: '你需要按时间和用户分组，这个教程刚好覆盖这个场景。',
      type: '教程'
    },
    {
      reason: '用于展示趋势变化，适合你的最终报告。',
      type: '课程'
    },
    {
      reason: '数据清洗是所有分析的第一步，一定要掌握。',
      type: '文档'
    }
  ]
};

export default function AgentMissionFeed({ resources, careerId, onOpenRAGDrawer }: AgentMissionFeedProps) {
  const recommendations = resourceRecommendations[careerId as keyof typeof resourceRecommendations] 
    || resourceRecommendations['software-engineer'];
  
  const limitedResources = resources.slice(0, 3);

  const getResourceIcon = (type: string) => {
    switch (type) {
      case '文档': return '📚';
      case '课程': return '🎓';
      case '教程': return '📖';
      case '练习': return '✏️';
      case '指南': return '📋';
      default: return '📄';
    }
  };

  const getRelevanceScore = () => {
    const scores = ['高', '中', '中'];
    return scores;
  };

  const relevanceScores = getRelevanceScore();

  return (
    <PixelCard title="📚 AI 推荐资源 (RAG)">
      <div className="space-y-3">
        <p className="text-slate-400 text-xs mb-3">
          基于任务分析，为你推荐以下资源：
        </p>
        {limitedResources.map((resource, index) => (
          <div
            key={resource.id}
            className="p-3 bg-slate-800/70 border-2 border-slate-700 hover:border-amber-500 transition-all cursor-pointer"
            onClick={onOpenRAGDrawer}
          >
            <div className="flex items-start gap-3">
              <span className="text-2xl">{getResourceIcon(resource.type)}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-slate-200 font-bold text-sm">{resource.title}</h4>
                  <PixelBadge variant="neutral" className="text-xs">
                    {recommendations[index]?.type || resource.type}
                  </PixelBadge>
                  <PixelBadge 
                    variant={relevanceScores[index] === '高' ? 'success' : 'neutral'} 
                    className="text-xs"
                  >
                    {relevanceScores[index]}相关
                  </PixelBadge>
                </div>
                <p className="text-slate-400 text-xs leading-snug">
                  👉 {recommendations[index]?.reason || '学习这个对你会有帮助。'}
                </p>
              </div>
            </div>
          </div>
        ))}
        
        {/* RAG 检索按钮 */}
        {onOpenRAGDrawer && (
          <div className="mt-4 pt-4 border-t-2 border-slate-700">
            <PixelButton 
              variant="primary" 
              className="w-full"
              onClick={onOpenRAGDrawer}
            >
              🔍 寻找更多资源（RAG 检索）
            </PixelButton>
          </div>
        )}
      </div>
    </PixelCard>
  );
}
