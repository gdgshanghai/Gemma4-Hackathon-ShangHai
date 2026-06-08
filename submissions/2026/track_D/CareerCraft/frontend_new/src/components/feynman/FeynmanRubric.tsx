'use client';

import React from 'react';
import { PixelBadge, PixelCard } from '@/components/pixel';

interface RubricItem {
  name: string;
  icon: string;
  score: number;
  maxScore: number;
}

interface FeynmanRubricProps {
  rubrics: RubricItem[];
}

export default function FeynmanRubric({ rubrics }: FeynmanRubricProps) {
  const totalScore = rubrics.reduce((sum, item) => sum + item.score, 0);
  const maxTotalScore = rubrics.reduce((sum, item) => sum + item.maxScore, 0);

  return (
    <PixelCard className="mb-6 bg-slate-950/82">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-bold text-amber-300">评分标准</h3>
        <PixelBadge variant="honor">
          总分 {totalScore} / {maxTotalScore}
        </PixelBadge>
      </div>

      <div className="space-y-3">
        {rubrics.map((item) => {
          const percent = (item.score / item.maxScore) * 100;
          return (
            <div key={item.name} className="border-2 border-slate-700 bg-slate-900/75 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center border-2 border-slate-600 text-xs text-amber-300">
                    {item.icon}
                  </span>
                  <span className="font-medium text-slate-200">{item.name}</span>
                </div>
                <PixelBadge variant={percent >= 80 ? 'success' : percent >= 60 ? 'warning' : 'danger'}>
                  {item.score} / {item.maxScore}
                </PixelBadge>
              </div>
              <div className="h-3 border-2 border-slate-700 bg-slate-800">
                <div
                  className={percent >= 80 ? 'h-full bg-emerald-500' : percent >= 60 ? 'h-full bg-amber-500' : 'h-full bg-red-500'}
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </PixelCard>
  );
}
