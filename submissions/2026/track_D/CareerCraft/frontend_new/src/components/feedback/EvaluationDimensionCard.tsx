import React from 'react';
import { PixelCard, PixelProgress, PixelBadge } from '@/components/pixel';

interface EvaluationDimensionProps {
  title: string;
  score: number;
  maxScore: number;
  observation: string;
}

export default function EvaluationDimensionCard({
  title,
  score,
  maxScore,
  observation,
}: EvaluationDimensionProps) {
  const percentage = (score / maxScore) * 100;
  const color = percentage >= 85 ? '#10b981' : percentage >= 70 ? '#f59e0b' : '#ef4444';
  const label = percentage >= 85 ? '优秀' : percentage >= 70 ? '达标' : '需补强';

  return (
    <PixelCard title={title} className="bg-slate-900/80">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-2xl font-bold text-amber-300">{score}</span>
            <span className="ml-1 text-sm text-slate-500">/ {maxScore}</span>
          </div>
          <PixelBadge variant={percentage >= 85 ? 'success' : percentage >= 70 ? 'warning' : 'danger'}>
            {label}
          </PixelBadge>
        </div>
        <PixelProgress value={percentage} color={color} />
        <div className="border-2 border-slate-700 bg-slate-950/60 p-3">
          <p className="mb-1 text-xs font-bold text-amber-300">导师观察</p>
          <p className="text-sm leading-6 text-slate-300">{observation}</p>
        </div>
      </div>
    </PixelCard>
  );
}
