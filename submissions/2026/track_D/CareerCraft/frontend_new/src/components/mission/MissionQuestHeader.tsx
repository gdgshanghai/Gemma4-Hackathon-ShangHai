import React from 'react';
import { PixelBadge } from '@/components/pixel';
import { BadgeVariant } from '@/constants/designSystem';
import { Mission, MissionStatus } from '@/types';

interface MissionQuestHeaderProps {
  mission: Mission;
  careerName: string;
}

const STATUS_COLORS: Record<MissionStatus, BadgeVariant> = {
  [MissionStatus.AVAILABLE]: 'neutral',
  [MissionStatus.ACCEPTED]: 'warning',
  [MissionStatus.SUBMITTED]: 'neutral',
  [MissionStatus.COMPLETED]: 'success',
  [MissionStatus.LOCKED]: 'neutral',
};

const STATUS_LABELS: Record<MissionStatus, string> = {
  [MissionStatus.AVAILABLE]: '可接受',
  [MissionStatus.ACCEPTED]: '进行中',
  [MissionStatus.SUBMITTED]: '待评审',
  [MissionStatus.COMPLETED]: '已完成',
  [MissionStatus.LOCKED]: '未解锁',
};

export default function MissionQuestHeader({ mission, careerName }: MissionQuestHeaderProps) {
  return (
    <section className="border-2 border-slate-700 bg-slate-950/86 p-6 backdrop-blur-sm">
      <div className="mb-3 font-mono text-xs uppercase tracking-[0.22em] text-emerald-300">
        Work Order
      </div>
      <h1 className="pixel-title text-2xl font-bold leading-tight text-amber-300">
        {mission.title}
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
        你收到了一份来自职业岛的真实委托。先理解背景，再拆解目标，最后提交可评审的成果。
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <PixelBadge variant={difficultyVariant(mission.difficulty)}>
          {difficultyLabel(mission.difficulty)}
        </PixelBadge>
        <PixelBadge variant={STATUS_COLORS[mission.status]}>
          {STATUS_LABELS[mission.status]}
        </PixelBadge>
        <PixelBadge variant="honor">+{mission.rewardExp} XP</PixelBadge>
        <PixelBadge variant="neutral">{careerName || '职业岛'}</PixelBadge>
      </div>
    </section>
  );
}

function difficultyLabel(difficulty: Mission['difficulty']) {
  if (difficulty === 'easy') return '入门委托';
  if (difficulty === 'medium') return '进阶委托';
  return '挑战委托';
}

function difficultyVariant(difficulty: Mission['difficulty']): BadgeVariant {
  if (difficulty === 'easy') return 'neutral';
  if (difficulty === 'medium') return 'warning';
  return 'success';
}
