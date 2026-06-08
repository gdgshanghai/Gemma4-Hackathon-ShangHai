import React, { useEffect, useMemo, useState } from 'react';
import { PixelCard, PixelProgress } from '@/components/pixel';

const CHECKLIST_ITEMS = [
  { id: 'background', label: '交代了任务背景和目标' },
  { id: 'problems', label: '列出了关键问题或假设' },
  { id: 'deliverables', label: '交付物完整可读' },
  { id: 'solution', label: '说明了分析或实现思路' },
  { id: 'criteria', label: '对照评分标准做过自检' },
];

interface SubmissionChecklistProps {
  missionId: string;
}

export default function SubmissionChecklist({ missionId }: SubmissionChecklistProps) {
  const storageKey = `careercraft-submission-checklist-${missionId}`;

  const [checklist, setChecklist] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    setChecklist(saved ? JSON.parse(saved) : {});
  }, [storageKey]);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(checklist));
  }, [checklist, storageKey]);

  const completedItems = useMemo(
    () => Object.values(checklist).filter(Boolean).length,
    [checklist],
  );
  const progressPercent = (completedItems / CHECKLIST_ITEMS.length) * 100;

  return (
    <PixelCard title="交付自检">
      <div className="space-y-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-300">准备度</span>
          <span className="font-bold text-amber-300">
            {completedItems} / {CHECKLIST_ITEMS.length}
          </span>
        </div>
        <PixelProgress
          value={progressPercent}
          color={completedItems >= 4 ? '#10b981' : completedItems >= 2 ? '#f59e0b' : '#ef4444'}
        />

        <div className="space-y-2">
          {CHECKLIST_ITEMS.map((item) => {
            const isChecked = Boolean(checklist[item.id]);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() =>
                  setChecklist((prev) => ({
                    ...prev,
                    [item.id]: !prev[item.id],
                  }))
                }
                className={`w-full border-2 p-3 text-left text-sm transition ${
                  isChecked
                    ? 'border-emerald-500 bg-emerald-950/40 text-emerald-100'
                    : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:border-amber-500'
                }`}
              >
                <span className="mr-3 inline-flex h-5 w-5 items-center justify-center border-2 border-current text-xs">
                  {isChecked ? '✓' : ''}
                </span>
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </PixelCard>
  );
}
