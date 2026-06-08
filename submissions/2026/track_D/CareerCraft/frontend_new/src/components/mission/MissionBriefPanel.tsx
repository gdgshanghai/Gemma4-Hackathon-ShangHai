import React from 'react';
import { PixelBadge, PixelCard } from '@/components/pixel';
import { Mission, MissionStatus } from '@/types';
import { useMissionStore } from '@/stores/missionStore';

interface MissionBriefPanelProps {
  mission: Mission;
}

export default function MissionBriefPanel({ mission }: MissionBriefPanelProps) {
  const { getMissionStatus } = useMissionStore();
  const currentStatus = getMissionStatus(mission.id, mission.status);

  const difficultyBadge = getDifficultyBadge(mission.difficulty);
  const statusBadge = getStatusBadge(currentStatus);

  return (
    <div className="space-y-4">
      <div className="border-2 border-slate-700 bg-slate-950 p-4">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">Mission Brief</div>
        <h3 className="mt-2 text-xl font-bold text-amber-300">{mission.title}</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          <PixelBadge variant={difficultyBadge.variant}>{difficultyBadge.text}</PixelBadge>
          <PixelBadge variant={statusBadge.variant}>{statusBadge.text}</PixelBadge>
          <PixelBadge variant="honor">+{mission.rewardExp} XP</PixelBadge>
        </div>
      </div>

      <div className="border-2 border-slate-700 bg-slate-950 p-4">
        <h4 className="font-bold text-amber-300">任务背景</h4>
        <p className="mt-2 text-sm leading-6 text-slate-300">{mission.background}</p>
      </div>

      <div className="border-2 border-slate-700 bg-slate-950 p-4">
        <h4 className="font-bold text-amber-300">任务目标</h4>
        <ul className="mt-2 space-y-2">
          {mission.objectives?.map((obj, idx) => (
            <li key={idx} className="flex items-start gap-3 text-sm leading-6 text-slate-300">
              <span className="font-mono font-bold text-amber-400">OBJ</span>
              <span>{obj}</span>
            </li>
          ))}
        </ul>
      </div>

      {mission.deliverables && mission.deliverables.length > 0 && (
        <div className="border-2 border-slate-700 bg-slate-950 p-4">
          <h4 className="font-bold text-amber-300">交付物</h4>
          <ul className="mt-2 space-y-2">
            {mission.deliverables.map((deliverable, idx) => (
              <li key={idx} className="flex items-start gap-3 text-sm leading-6 text-slate-300">
                <span className="font-mono font-bold text-emerald-400">OUT</span>
                <span>{deliverable}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {mission.criteria && mission.criteria.length > 0 && (
        <div className="border-2 border-slate-700 bg-slate-950 p-4">
          <h4 className="font-bold text-amber-300">评审标准</h4>
          <div className="mt-3 flex flex-wrap gap-2">
            {mission.criteria.map((criteria, idx) => (
              <PixelBadge key={idx} variant="neutral">{criteria}</PixelBadge>
            ))}
          </div>
        </div>
      )}

      {mission.rewardSkills && mission.rewardSkills.length > 0 && (
        <div className="border-2 border-slate-700 bg-slate-950 p-4">
          <h4 className="font-bold text-amber-300">关联技能</h4>
          <div className="mt-3 flex flex-wrap gap-2">
            {mission.rewardSkills.map((skill) => (
              <PixelBadge key={skill} variant="fun">{skill}</PixelBadge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function getDifficultyBadge(difficulty: string) {
  switch (difficulty) {
    case 'easy':
      return { variant: 'fun' as const, text: '入门' };
    case 'medium':
      return { variant: 'honor' as const, text: '中等' };
    case 'hard':
      return { variant: 'warning' as const, text: '困难' };
    default:
      return { variant: 'neutral' as const, text: '未知' };
  }
}

function getStatusBadge(status: MissionStatus) {
  switch (status) {
    case MissionStatus.LOCKED:
      return { variant: 'neutral' as const, text: '未解锁' };
    case MissionStatus.AVAILABLE:
      return { variant: 'fun' as const, text: '可接受' };
    case MissionStatus.ACCEPTED:
      return { variant: 'honor' as const, text: '进行中' };
    case MissionStatus.SUBMITTED:
      return { variant: 'neutral' as const, text: '评审中' };
    case MissionStatus.COMPLETED:
      return { variant: 'honor' as const, text: '已完成' };
    default:
      return { variant: 'neutral' as const, text: '未知' };
  }
}
