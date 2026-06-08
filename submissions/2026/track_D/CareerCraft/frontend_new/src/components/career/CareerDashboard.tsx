'use client';

import React, { useCallback } from 'react';
import { PixelBadge, PixelButton, PixelProgress } from '@/components/pixel';
import { Mission, MissionStatus, SkillNode } from '@/types';
import { useMissionStore } from '@/stores/missionStore';

interface CareerDashboardProps {
  missions: Mission[];
  skills: SkillNode[];
}

const STATUS_LABELS: Record<MissionStatus, string> = {
  [MissionStatus.AVAILABLE]: '待领取',
  [MissionStatus.ACCEPTED]: '进行中',
  [MissionStatus.SUBMITTED]: '评审中',
  [MissionStatus.COMPLETED]: '已完成',
  [MissionStatus.LOCKED]: '未解锁',
};

export default function CareerDashboard({ missions, skills }: CareerDashboardProps) {
  const { getMissionStatus } = useMissionStore();

  const stats = React.useMemo(() => {
    const missionCounts = {
      [MissionStatus.AVAILABLE]: 0,
      [MissionStatus.ACCEPTED]: 0,
      [MissionStatus.SUBMITTED]: 0,
      [MissionStatus.COMPLETED]: 0,
      [MissionStatus.LOCKED]: 0,
    };
    let totalExp = 120;

    missions.forEach((mission) => {
      const status = getMissionStatus(mission.id, mission.status);
      missionCounts[status] += 1;
      if (status === MissionStatus.COMPLETED) totalExp += mission.rewardExp ?? 0;
    });

    const litSkills = skills.filter((skill) => (skill.level ?? 0) > 0).length;
    const progress = missions.length > 0
      ? Math.round((missionCounts[MissionStatus.COMPLETED] / missions.length) * 100)
      : 0;

    return { totalExp, litSkills, progress, missionCounts, totalMissions: missions.length, totalSkills: skills.length };
  }, [missions, skills, getMissionStatus]);

  const recommendedMission = React.useMemo(() => {
    return (
      missions.find((mission) => getMissionStatus(mission.id, mission.status) === MissionStatus.ACCEPTED) ??
      missions.find((mission) => getMissionStatus(mission.id, mission.status) === MissionStatus.AVAILABLE) ??
      null
    );
  }, [missions, getMissionStatus]);

  const handleViewMission = useCallback(() => {
    document.getElementById('career-task-board')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const statCards = [
    { label: '冒险等级', value: 'Lv.01', note: '校园探索者' },
    { label: '经验值', value: `${stats.totalExp} XP`, note: '来自任务与评审' },
    { label: '真实委托', value: `${stats.missionCounts[MissionStatus.COMPLETED]}/${stats.totalMissions}`, note: '完成后进入作品集' },
    { label: '技能水平', value: `${stats.litSkills}/${stats.totalSkills}`, note: '点亮岗位能力' },
  ];

  return (
    <section className="space-y-5">
      <div className="overflow-hidden border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
              Student Adventure Log
            </div>
            <h2 className="pixel-title text-2xl font-bold text-amber-300">职业试炼日志</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
              这不是一次性测评，而是一份会随着任务、反馈和作品集持续更新的职业规划草图。
            </p>
          </div>
          <PixelBadge variant="warning">主线同步中</PixelBadge>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {statCards.map((card) => (
            <div key={card.label} className="border border-slate-700 bg-slate-950/62 p-4">
              <div className="font-mono text-xs uppercase tracking-[0.16em] text-slate-500">{card.label}</div>
              <div className="mt-2 text-2xl font-bold text-amber-200">{card.value}</div>
              <div className="mt-2 text-xs leading-5 text-slate-400">{card.note}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="border-2 border-slate-700 bg-slate-950/84 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-amber-300">主线完成度</h3>
              <p className="text-sm text-slate-400">完成真实委托后，AI 评审会把能力证据写入成长档案。</p>
            </div>
            <span className="font-mono text-xl font-bold text-emerald-300">{stats.progress}%</span>
          </div>
          <PixelProgress value={stats.progress} color="#f59e0b" />
          <div className="mt-5 grid gap-3 sm:grid-cols-5">
            {Object.values(MissionStatus).map((status) => (
              <div key={status} className="border border-slate-700 bg-slate-900/58 p-3 text-center">
                <div className="text-xl font-bold text-amber-200">{stats.missionCounts[status]}</div>
                <div className="mt-1 text-xs text-slate-400">{STATUS_LABELS[status]}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="border-2 border-amber-700/75 bg-slate-950/86 p-5 backdrop-blur-sm">
          <div className="mb-3 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">Next Quest</div>
          {recommendedMission ? (
            <>
              <h3 className="mb-2 text-lg font-bold text-amber-300">{recommendedMission.title}</h3>
              <p className="mb-4 line-clamp-3 text-sm leading-6 text-slate-300">{recommendedMission.description}</p>
              <div className="mb-4 flex flex-wrap gap-2">
                <PixelBadge variant="warning">+{recommendedMission.rewardExp ?? 0} XP</PixelBadge>
                <PixelBadge variant="neutral">{difficultyLabel(recommendedMission.difficulty ?? 'medium')}</PixelBadge>
              </div>
              <PixelButton onClick={handleViewMission} fullWidth>
                前往任务看板
              </PixelButton>
            </>
          ) : (
            <p className="text-sm leading-6 text-slate-300">
              当前路线的委托正在建设中。你可以先查看技能路线，或使用 AI 生成一张新委托。
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function difficultyLabel(difficulty: Mission['difficulty']) {
  if (difficulty === 'easy') return '入门委托';
  if (difficulty === 'medium') return '进阶委托';
  return '高阶委托';
}
