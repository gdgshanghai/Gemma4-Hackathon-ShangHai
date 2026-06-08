import React from 'react';
import { PixelBadge, PixelProgress } from '@/components/pixel';

interface CareerProgressBannerProps {
  currentStage: string;
  nextStage: string;
  currentGoal: string;
  progress: number;
}

export default function CareerProgressBanner({
  currentStage,
  nextStage,
  currentGoal,
  progress,
}: CareerProgressBannerProps) {
  return (
    <section className="border-2 border-slate-700 bg-slate-950/84 p-5 backdrop-blur-sm">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-center">
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <PixelBadge variant="warning">主线 {progress}%</PixelBadge>
            <span className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
              Career Sketch Simulation
            </span>
          </div>
          <h3 className="mb-2 text-xl font-bold text-amber-300">
            {currentStage} → {nextStage}
          </h3>
          <p className="max-w-3xl text-sm leading-6 text-slate-400">
            当前页面记录你在这条职业路线里的位置：从兴趣探索，到岗位任务，再到作品集证据。
          </p>
        </div>

        <div className="border border-slate-700 bg-slate-950/70 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="font-mono text-xs uppercase tracking-[0.16em] text-slate-500">Current Quest</span>
            <span className="text-sm font-bold text-amber-300">Lv.01</span>
          </div>
          <PixelProgress value={progress} color="#f59e0b" />
          <p className="mt-3 text-sm leading-6 text-slate-300">{currentGoal}</p>
        </div>
      </div>
    </section>
  );
}
