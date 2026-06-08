import React from 'react';
import { PixelCard, PixelBadge } from '@/components/pixel';
import { Mission } from '@/types';
import { getRecommendResources } from '@/data/resources';

interface MissionResourceHintsProps {
  mission: Mission;
}

export default function MissionResourceHints({ mission }: MissionResourceHintsProps) {
  const careerId = mission.careerId || 'software-engineer';
  const resources = getRecommendResources(careerId).slice(0, 3);
  
  const getResourceIcon = (type: string) => {
    switch (type) {
      case '文档': return '📚';
      case '课程': return '🎓';
      case '教程': return '📖';
      case '练习': return '✏️';
      case '指南': return '📋';
      case '速查表': return '📝';
      case '规范': return '📏';
      case '模板': return '📄';
      case '案例': return '📊';
      case '平台': return '🌐';
      default: return '📄';
    }
  };
  
  return (
    <PixelCard title="📚 推荐资源">
      {resources.length === 0 ? (
        <div className="text-center py-6 text-slate-400 text-sm">
          暂无推荐资源
        </div>
      ) : (
        <div className="space-y-3">
          {resources.map((resource) => (
            <div
              key={resource.id}
              className="p-3 bg-slate-800 border-2 border-slate-700 hover:border-amber-500 transition-all duration-150"
              style={{
                boxShadow: 'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #475569'
              }}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl">{getResourceIcon(resource.type)}</span>
                <div className="flex-1">
                  <h4 className="text-slate-200 font-bold text-sm">{resource.title}</h4>
                  <div className="flex flex-wrap gap-1 mt-1">
                    <PixelBadge variant="neutral" className="text-xs">
                      {resource.type}
                    </PixelBadge>
                    <PixelBadge variant="fun" className="text-xs">
                      {resource.relevance}% 相关度
                    </PixelBadge>
                  </div>
                  {(resource.tags || []).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {(resource.tags || []).map((tag, idx) => (
                        <PixelBadge key={idx} variant="neutral" className="text-xs opacity-70">
                          {tag}
                        </PixelBadge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </PixelCard>
  );
}
