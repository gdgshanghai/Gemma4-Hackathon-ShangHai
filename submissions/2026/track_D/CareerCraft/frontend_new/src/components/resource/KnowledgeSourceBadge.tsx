'use client';

import React from 'react';
import { PixelBadge } from '@/components/pixel';

export interface KnowledgeSource {
  name: string;
  hitCount: number;
  confidence: '高' | '中' | '低';
  type: '任务脚本库' | '笔记库' | '案例库';
}

interface KnowledgeSourceBadgeProps {
  source: KnowledgeSource;
}

export default function KnowledgeSourceBadge({ source }: KnowledgeSourceBadgeProps) {
  const confidenceVariant = source.confidence === '高' ? 'success' : source.confidence === '中' ? 'neutral' : 'warning';
  const typeVariant = source.type === '任务脚本库' ? 'honor' : source.type === '笔记库' ? 'fun' : 'neutral';
  const sourceToken = source.type === '任务脚本库' ? 'QS' : source.type === '笔记库' ? 'NT' : 'CS';

  return (
    <div className="border-2 border-slate-600 bg-slate-900/90 p-4 transition-colors hover:border-amber-500">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-amber-600 bg-slate-950 font-mono text-sm font-bold text-amber-300">
            {sourceToken}
          </div>
          <h4 className="truncate text-base font-bold text-slate-100">{source.name}</h4>
        </div>
        <PixelBadge variant={typeVariant}>{source.type}</PixelBadge>
      </div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="text-slate-400">
          命中 <span className="font-bold text-amber-400">{source.hitCount}</span> 条档案
        </span>
        <PixelBadge variant={confidenceVariant}>可信度 {source.confidence}</PixelBadge>
      </div>
    </div>
  );
}
