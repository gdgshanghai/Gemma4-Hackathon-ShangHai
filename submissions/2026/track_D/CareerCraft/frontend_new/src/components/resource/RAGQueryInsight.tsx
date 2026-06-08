'use client';

import React from 'react';
import { PixelBadge, PixelCard } from '@/components/pixel';

interface RAGQueryInsightProps {
  taskType?: 'data-analyst' | 'software-engineer';
}

export default function RAGQueryInsight({ taskType = 'software-engineer' }: RAGQueryInsightProps) {
  const insight =
    taskType === 'data-analyst'
      ? {
          keywords: ['用户活跃度', '分组聚合', '趋势分析', '可视化报告'],
          learningNeed: '先弄清指标口径，再用分组统计定位变化区间，最后把结论写成能被业务同学理解的报告。',
          searchStrategy: '优先调取 Pandas 聚合、趋势图绘制、活跃用户分析模板和真实案例。',
        }
      : {
          keywords: ['Bug 复现', '日志定位', '单元测试', '回归验证'],
          learningNeed: '先复现问题，再从日志和边界条件里定位根因，最后用测试把修复结果固定下来。',
          searchStrategy: '优先调取调试流程、日志排查指南、测试用例示例和复盘模板。',
        };

  return (
    <PixelCard title="查询理解">
      <div className="space-y-4">
        <div>
          <div className="mb-2 text-sm font-bold text-amber-300">识别到关键词</div>
          <div className="flex flex-wrap gap-2">
            {insight.keywords.map((keyword) => (
              <PixelBadge key={keyword} variant="fun">
                {keyword}
              </PixelBadge>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 text-sm font-bold text-amber-300">推断学习需求</div>
          <p className="border-2 border-slate-700 bg-slate-950 p-3 leading-7 text-slate-200">
            {insight.learningNeed}
          </p>
        </div>

        <div>
          <div className="mb-2 text-sm font-bold text-amber-300">推荐检索策略</div>
          <p className="border-2 border-slate-700 bg-slate-950 p-3 leading-7 text-slate-200">
            {insight.searchStrategy}
          </p>
        </div>
      </div>
    </PixelCard>
  );
}
