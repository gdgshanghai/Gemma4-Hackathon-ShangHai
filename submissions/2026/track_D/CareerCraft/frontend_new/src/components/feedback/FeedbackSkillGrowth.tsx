import React from 'react';
import { PixelBadge, PixelCard, PixelProgress } from '@/components/pixel';

interface SkillGrowth {
  name: string;
  xp: number;
  progress?: number;
}

interface FeedbackSkillGrowthProps {
  skills: SkillGrowth[];
  badge: string;
  totalXP: number;
}

export default function FeedbackSkillGrowth({ skills, badge, totalXP }: FeedbackSkillGrowthProps) {
  return (
    <>
      <PixelCard title="获得徽章">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-24 w-24 items-center justify-center border-4 border-amber-500 bg-amber-950/50">
            <span className="pixel-title text-3xl text-amber-200">★</span>
          </div>
          <PixelBadge variant="honor" className="text-base">
            {badge}
          </PixelBadge>
        </div>
      </PixelCard>

      <PixelCard title="技能成长">
        <div className="mb-4 text-center">
          <span className="text-2xl font-bold text-emerald-300">+{totalXP} XP</span>
        </div>
        <div className="space-y-3">
          {skills.map((skill) => {
            const progress = skill.progress || 70;
            return (
              <div key={skill.name} className="border-2 border-slate-700 bg-slate-900/70 p-3">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-sm font-bold text-slate-200">{skill.name}</span>
                  <span className="font-mono text-sm text-emerald-300">+{skill.xp} XP</span>
                </div>
                <PixelProgress value={progress} color={progress >= 80 ? '#10b981' : '#f59e0b'} />
              </div>
            );
          })}
        </div>
      </PixelCard>
    </>
  );
}
