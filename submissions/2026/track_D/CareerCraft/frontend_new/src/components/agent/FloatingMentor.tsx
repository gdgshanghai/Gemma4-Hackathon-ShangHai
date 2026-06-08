'use client';

import React, { useEffect, useMemo, useState } from 'react';
import AgentChat from './AgentChat';
import { getMentorStateSheet } from '@/constants/images';
import { getCareerMentor, MentorMood, MentorStage } from '@/data';

interface FloatingMentorProps {
  careerId: string;
  stage?: MentorStage;
  missionTitle?: string;
  pageTopic?: string;
  cue?: string;
  mood?: MentorMood;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const moodPositions: Record<MentorMood, string> = {
  idle: '0% center',
  thinking: '25% center',
  warning: '50% center',
  encouraging: '75% center',
  celebrating: '100% center',
};

const moodMeta: Record<MentorMood, { label: string; border: string; chip: string }> = {
  idle: { label: '巡航', border: 'border-emerald-400/70', chip: 'bg-emerald-400 text-slate-950' },
  thinking: { label: '思考', border: 'border-sky-400/80', chip: 'bg-sky-400 text-slate-950' },
  warning: { label: '提醒', border: 'border-rose-400/80', chip: 'bg-rose-400 text-slate-950' },
  encouraging: { label: '鼓励', border: 'border-amber-400/80', chip: 'bg-amber-400 text-slate-950' },
  celebrating: { label: '庆祝', border: 'border-yellow-300', chip: 'bg-yellow-300 text-slate-950' },
};

export default function FloatingMentor({
  careerId,
  stage = 'career',
  missionTitle,
  pageTopic,
  cue,
  mood = 'idle',
  open,
  onOpenChange,
}: FloatingMentorProps) {
  const mentor = useMemo(() => getCareerMentor(careerId), [careerId]);
  const [internalOpen, setInternalOpen] = useState(false);
  const [bubbleIndex, setBubbleIndex] = useState(0);
  const [hovered, setHovered] = useState(false);
  const isOpen = open ?? internalOpen;
  const meta = moodMeta[mood];
  const reactions = mentor.reactions[mood];
  const bubble = cue || (hovered ? `我是${mentor.name}。点我打开导师终端，我们一起拆问题。` : reactions[bubbleIndex % reactions.length]);

  const setOpen = (next: boolean) => {
    setInternalOpen(next);
    onOpenChange?.(next);
  };

  useEffect(() => {
    if (cue || hovered) return;
    const timer = window.setInterval(() => setBubbleIndex((value) => value + 1), 5200);
    return () => window.clearInterval(timer);
  }, [cue, hovered]);

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 w-[min(92vw,430px)]">
      {isOpen ? (
        <div className="pointer-events-auto mb-3 overflow-hidden border-4 border-amber-700 bg-slate-950 shadow-[0_22px_70px_rgba(2,6,23,0.72)]">
          <div className="flex items-center justify-between border-b-2 border-slate-700 bg-slate-900 px-3 py-2">
            <div>
              <p className="pixel-title text-sm text-amber-300">导师终端</p>
              <p className="text-xs text-slate-400">
                {mentor.name} / {mentor.title}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="border-2 border-slate-600 bg-slate-800 px-2 py-1 font-mono text-xs text-slate-200 hover:border-amber-500"
              aria-label="关闭导师终端"
            >
              X
            </button>
          </div>
          <AgentChat
            careerId={careerId}
            stage={stage}
            missionTitle={missionTitle}
            pageTopic={pageTopic}
            compact
            className="border-0 shadow-none"
          />
        </div>
      ) : null}

      <div className="pointer-events-auto flex items-end justify-end gap-3">
        {!isOpen ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="max-w-[280px] border-2 border-slate-700 bg-slate-950/95 px-3 py-2 text-left text-xs leading-5 text-slate-200 shadow-[0_12px_30px_rgba(2,6,23,0.45)] transition hover:-translate-y-0.5 hover:border-amber-500"
          >
            <span className="mb-1 flex items-center justify-between gap-3">
              <span className="font-bold text-amber-300">{mentor.name}</span>
              <span className={`px-1.5 py-0.5 font-mono text-[10px] font-black ${meta.chip}`}>{meta.label}</span>
            </span>
            {bubble}
          </button>
        ) : null}

        <button
          type="button"
          onClick={() => setOpen(!isOpen)}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          className={`group relative h-36 w-28 overflow-hidden border-4 bg-slate-950 shadow-[0_0_0_2px_rgba(15,23,42,0.9),0_16px_36px_rgba(2,6,23,0.55)] transition hover:-translate-y-1 ${meta.border}`}
          aria-label={isOpen ? '收起导师对话' : '打开导师对话'}
        >
          <span
            aria-hidden="true"
            className="absolute inset-0 bg-no-repeat transition-transform duration-300 group-hover:scale-105"
            style={{
              backgroundImage: `url(${getMentorStateSheet(careerId)})`,
              backgroundPosition: moodPositions[mood],
              backgroundSize: '500% 100%',
            }}
          />
          <span className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[length:100%_6px] opacity-35" />
          <span className="absolute left-2 top-2 h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.9)]" />
          <span className="absolute right-2 top-2 border border-slate-900 bg-slate-950/85 px-1 font-mono text-[9px] font-black text-amber-200">
            {meta.label}
          </span>
          <span className="absolute bottom-2 left-2 border border-slate-900 bg-amber-500 px-1 font-mono text-[10px] font-black text-slate-950">
            {mentor.avatar}
          </span>
        </button>
      </div>
    </div>
  );
}
