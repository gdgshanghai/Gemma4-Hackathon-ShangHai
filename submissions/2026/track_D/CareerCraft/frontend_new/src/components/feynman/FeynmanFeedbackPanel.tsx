'use client';

import React from 'react';
import { PixelBadge, PixelButton } from '@/components/pixel';

interface Feedback {
  score: number;
  maxScore: number;
  rating: string;
  aiFeedback: string;
  strengths: string[];
  improvements: string[];
  badgeEarned: boolean;
}

interface FeynmanFeedbackPanelProps {
  feedback: Feedback;
  onBackToMission: () => void;
  onBackToSubmit: () => void;
  onRetry: () => void;
}

export default function FeynmanFeedbackPanel({
  feedback,
  onBackToMission,
  onBackToSubmit,
  onRetry,
}: FeynmanFeedbackPanelProps) {
  return (
    <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
      <section className="border-4 border-slate-700 bg-slate-950/82 p-5 text-center backdrop-blur-sm">
        <div className="text-4xl font-bold text-amber-300">{feedback.score}</div>
        <div className="mt-1 text-sm text-slate-500">/ {feedback.maxScore}</div>
        <div className="mt-4">
          <PixelBadge variant={feedback.score >= 80 ? 'success' : feedback.score >= 60 ? 'warning' : 'neutral'}>
            {feedback.rating}
          </PixelBadge>
        </div>
        {feedback.badgeEarned ? (
          <div className="mt-4 border-2 border-amber-700 bg-amber-950/25 p-3 text-sm font-bold text-amber-200">
            获得理解力徽章
          </div>
        ) : null}
      </section>

      <section className="space-y-4">
        <div className="border-4 border-slate-700 bg-slate-950/82 p-5 backdrop-blur-sm">
          <h3 className="mb-3 font-bold text-amber-300">AI 反馈</h3>
          <p className="text-sm leading-7 text-slate-300">{feedback.aiFeedback}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <FeedbackList title="做得好的地方" items={feedback.strengths} tone="success" />
          <FeedbackList title="可以改进" items={feedback.improvements} tone="warning" />
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <PixelButton onClick={onBackToMission}>回到任务</PixelButton>
          <PixelButton onClick={onBackToSubmit} variant="secondary">
            回到提交页
          </PixelButton>
          <PixelButton onClick={onRetry} variant="ghost">
            再挑战一次
          </PixelButton>
        </div>
      </section>
    </div>
  );
}

function FeedbackList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: 'success' | 'warning';
}) {
  return (
    <div className="border-4 border-slate-700 bg-slate-950/82 p-5 backdrop-blur-sm">
      <h3 className="mb-3 font-bold text-amber-300">{title}</h3>
      <ul className="space-y-2">
        {(items.length > 0 ? items : ['暂无']).map((item, index) => (
          <li key={index} className="flex gap-2 text-sm leading-6 text-slate-300">
            <span className={`mt-2 h-2 w-2 shrink-0 ${tone === 'success' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
