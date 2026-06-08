import React from 'react';
import { PixelBadge } from '@/components/pixel';
import { Mission } from '@/types';

interface MissionBriefScrollProps {
  mission: Mission;
}

export default function MissionBriefScroll({ mission }: MissionBriefScrollProps) {
  return (
    <section className="border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
      <div className="mb-5">
        <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-300">Mission Brief</div>
        <h2 className="mt-2 text-xl font-bold text-amber-300">任务说明书</h2>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <InfoBlock badge="1" title="任务背景">
          <p>{mission.background || mission.description}</p>
        </InfoBlock>
        <InfoBlock badge="2" title="为什么重要">
          <p>这类任务会训练你从真实问题出发，完成分析、判断和表达，而不是只停留在概念学习。</p>
        </InfoBlock>
      </div>

      <div className="mt-4">
        <InfoBlock badge="3" title="任务目标">
          <ul className="space-y-2">
            {mission.objectives.map((objective, index) => (
              <li key={index} className="flex gap-2">
                <span className="mt-2 h-2 w-2 shrink-0 bg-amber-400" />
                <span>{objective}</span>
              </li>
            ))}
          </ul>
        </InfoBlock>
      </div>

      {mission.rewardSkills.length > 0 && (
        <div className="mt-4">
          <InfoBlock badge="4" title="会训练的能力">
            <div className="flex flex-wrap gap-2">
              {mission.rewardSkills.map((skill) => (
                <span key={skill} className="border border-slate-600 bg-slate-900/70 px-3 py-1 text-sm text-slate-300">
                  {skill}
                </span>
              ))}
            </div>
          </InfoBlock>
        </div>
      )}
    </section>
  );
}

function InfoBlock({ badge, title, children }: { badge: string; title: string; children: React.ReactNode }) {
  return (
    <div className="border border-slate-700 bg-slate-900/56 p-4 text-sm leading-6 text-slate-300">
      <div className="mb-2 flex items-center gap-2">
        <PixelBadge variant="warning">{badge}</PixelBadge>
        <h3 className="font-bold text-slate-100">{title}</h3>
      </div>
      {children}
    </div>
  );
}
