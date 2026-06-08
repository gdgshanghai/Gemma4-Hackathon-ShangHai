import React from 'react';
import { PixelBadge, PixelCard, PixelProgress } from '@/components/pixel';

interface FeedbackScoreCardProps {
  totalScore: number;
  maxScore: number;
  grade: string;
  conclusion: string;
}

export default function FeedbackScoreCard({
  totalScore,
  maxScore,
  grade,
  conclusion,
}: FeedbackScoreCardProps) {
  const percent = (totalScore / maxScore) * 100;
  const color = percent >= 85 ? '#10b981' : percent >= 70 ? '#f59e0b' : '#ef4444';

  return (
    <PixelCard title="结算面板">
      <div className="space-y-5 text-center">
        <div className="mx-auto flex h-28 w-28 items-center justify-center border-4 border-amber-500 bg-amber-950/50">
          <span className="pixel-title text-5xl text-amber-300">{grade}</span>
        </div>
        <div>
          <p className="text-3xl font-bold text-amber-300">
            {totalScore}
            <span className="text-base text-slate-500"> / {maxScore}</span>
          </p>
          <PixelProgress value={percent} color={color} />
        </div>
        <PixelBadge variant={percent >= 70 ? 'success' : 'warning'}>{conclusion}</PixelBadge>
      </div>
    </PixelCard>
  );
}
