import React from 'react';
import { getMentorImage } from '@/constants/images';

interface MissionMentorHintProps {
  careerId: string;
}

const MENTOR_CONFIG = {
  'software-engineer': {
    mentorName: '架构导师',
    hint: '先复现，再定位，最后修复。不要跳过问题边界。',
  },
  'data-analyst': {
    mentorName: '数据领航员',
    hint: '先确认指标口径，再做清洗和分组分析。',
  },
};

export default function MissionMentorHint({ careerId }: MissionMentorHintProps) {
  const config = MENTOR_CONFIG[careerId as keyof typeof MENTOR_CONFIG] ??
    MENTOR_CONFIG['software-engineer'];
  const mentorImage = getMentorImage(careerId);

  return (
    <aside className="border-2 border-amber-700/75 bg-slate-950/86 p-5 backdrop-blur-sm">
      <div className="mb-4 flex items-center gap-3">
        <img src={mentorImage} alt="mentor portrait" className="h-14 w-14 border-2 border-amber-600 object-cover" />
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">Mentor Hint</div>
          <h3 className="mt-1 font-bold text-amber-300">{config.mentorName}</h3>
        </div>
      </div>
      <p className="text-sm leading-6 text-slate-300">{config.hint}</p>
    </aside>
  );
}
