import React, { useEffect, useState } from 'react';
import { PixelCard, PixelProgress } from '@/components/pixel';
import { Mission } from '@/types';

interface MissionChecklistProps {
  mission: Mission;
}

const CHECKLIST_ITEMS = [
  { id: 'understand', label: '我已理解任务背景' },
  { id: 'key-questions', label: '我已列出关键问题' },
  { id: 'deliverables', label: '我已完成交付物' },
  { id: 'review', label: '我已对照评分标准检查' },
  { id: 'submit', label: '我已准备提交给 AI 导师' },
];

export default function MissionChecklist({ mission }: MissionChecklistProps) {
  const storageKey = `careercraft-checklist-${mission.id}`;

  const getInitialChecklist = () => {
    if (typeof window === 'undefined') return {} as Record<string, boolean>;

    const stored = localStorage.getItem(storageKey);
    if (!stored) return {};

    try {
      return JSON.parse(stored) as Record<string, boolean>;
    } catch {
      return {};
    }
  };

  const [checklist, setChecklist] = useState<Record<string, boolean>>(getInitialChecklist);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(checklist));
  }, [checklist, storageKey]);

  const completedItems = Object.values(checklist).filter(Boolean).length;
  const progress = Math.round((completedItems / CHECKLIST_ITEMS.length) * 100);

  const toggleCheck = (itemId: string) => {
    setChecklist((prev) => ({
      ...prev,
      [itemId]: !prev[itemId],
    }));
  };

  return (
    <PixelCard title="任务检查清单">
      <div className="space-y-4">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm text-slate-400">完成进度</span>
            <span className="text-sm font-bold text-amber-400">
              {completedItems}/{CHECKLIST_ITEMS.length}
            </span>
          </div>
          <PixelProgress value={progress} color={progress === 100 ? '#10b981' : '#f59e0b'} />
        </div>

        <div className="space-y-2">
          {CHECKLIST_ITEMS.map((item) => {
            const isChecked = checklist[item.id] || false;

            return (
              <button
                key={item.id}
                onClick={() => toggleCheck(item.id)}
                className={`w-full border-2 p-3 text-left transition-all duration-150 ${
                  isChecked ? 'border-emerald-700 bg-emerald-950/30' : 'border-slate-700 bg-slate-950 hover:border-amber-500'
                }`}
                style={{
                  boxShadow: isChecked
                    ? 'inset -2px -2px 0px 0px #052e1a, inset 2px 2px 0px 0px #065f46'
                    : 'inset -2px -2px 0px 0px #020617, inset 2px 2px 0px 0px #334155',
                }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-5 w-5 items-center justify-center border-2 ${
                      isChecked ? 'border-emerald-500 bg-emerald-600' : 'border-slate-600 bg-slate-800'
                    }`}
                  >
                    {isChecked ? <span className="text-xs font-bold text-white">✓</span> : null}
                  </div>
                  <span className={`text-sm ${isChecked ? 'text-emerald-300 line-through' : 'text-slate-300'}`}>
                    {item.label}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-6 space-y-4 border-t-2 border-slate-700 pt-4">
          <ChecklistBlock title="交付物清单" marker="OUT" items={mission.deliverables || []} />
          <ChecklistBlock title="评审标准" marker="QA" items={mission.criteria || []} />
        </div>
      </div>
    </PixelCard>
  );
}

function ChecklistBlock({ title, marker, items }: { title: string; marker: string; items: string[] }) {
  return (
    <div className="border-2 border-slate-700 bg-slate-950 p-3">
      <h4 className="mb-2 font-bold text-amber-300">{title}</h4>
      <ul className="space-y-1">
        {items.map((item, index) => (
          <li key={`${marker}-${index}`} className="flex items-start gap-2 text-sm leading-6 text-slate-300">
            <span className="font-mono text-amber-400">{marker}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
