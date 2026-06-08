import React from 'react';
import { PixelCard, PixelProgress } from '@/components/pixel';

interface Dimension {
  name: string;
  score: number;
  maxScore: number;
  color: string;
  description?: string;
}

interface FeedbackDimensionBreakdownProps {
  dimensions: Dimension[];
}

export default function FeedbackDimensionBreakdown({ dimensions }: FeedbackDimensionBreakdownProps) {
  return (
    <PixelCard title="评分拆解">
      <div className="space-y-4">
        {dimensions.map((dimension) => (
          <div key={dimension.name} className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-bold text-slate-200">{dimension.name}</span>
              <span className="font-mono text-sm text-amber-300">
                {dimension.score}/{dimension.maxScore}
              </span>
            </div>
            <PixelProgress
              value={(dimension.score / dimension.maxScore) * 100}
              color={dimension.color}
            />
            {dimension.description ? (
              <p className="text-xs leading-5 text-slate-500">{dimension.description}</p>
            ) : null}
          </div>
        ))}
      </div>
    </PixelCard>
  );
}
