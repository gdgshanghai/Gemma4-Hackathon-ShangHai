import React from 'react';
import { PixelCard } from '@/components/pixel';

interface TimelineItem {
  id: string;
  title: string;
  icon: string;
  completed: boolean;
}

interface FeedbackReviewTimelineProps {
  items?: TimelineItem[];
}

const defaultItems: TimelineItem[] = [
  { id: 'submitted', title: '学生提交', icon: '1', completed: true },
  { id: 'screening', title: 'AI 初审', icon: '2', completed: true },
  { id: 'mentor', title: '导师复盘', icon: '3', completed: true },
  { id: 'growth', title: '技能结算', icon: '4', completed: true },
];

export default function FeedbackReviewTimeline({ items = defaultItems }: FeedbackReviewTimelineProps) {
  return (
    <PixelCard title="评审进度">
      <div className="space-y-1">
        {items.map((item, index) => (
          <div key={item.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div
                className={`flex h-9 w-9 items-center justify-center border-2 text-xs font-bold ${
                  item.completed
                    ? 'border-emerald-500 bg-emerald-950/60 text-emerald-200'
                    : 'border-slate-700 bg-slate-900 text-slate-400'
                }`}
              >
                {item.icon}
              </div>
              {index < items.length - 1 ? <div className="h-7 w-0.5 bg-slate-700" /> : null}
            </div>
            <div className="pt-2 text-sm font-bold text-slate-200">{item.title}</div>
          </div>
        ))}
      </div>
    </PixelCard>
  );
}
