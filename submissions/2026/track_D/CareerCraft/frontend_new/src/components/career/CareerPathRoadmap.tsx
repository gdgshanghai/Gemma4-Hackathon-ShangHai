'use client';

import React from 'react';
import { PixelBadge, PixelProgress } from '@/components/pixel';
import { getCareerPlaybook } from '@/data';
import { Mission, MissionStatus } from '@/types';
import { useMissionStore } from '@/stores/missionStore';

interface CareerPathRoadmapProps {
  careerId: string;
  missions: Mission[];
}

export default function CareerPathRoadmap({ careerId, missions = [] }: CareerPathRoadmapProps) {
  const { missionStatuses } = useMissionStore();
  const playbook = getCareerPlaybook(careerId);
  const stages = playbook.roadmaps;

  const completedMissionCount = missions.filter((mission) => {
    const status = missionStatuses[mission.id] || mission.status;
    return status === MissionStatus.COMPLETED;
  }).length;
  const progress = missions.length > 0 ? Math.round((completedMissionCount / missions.length) * 100) : 0;

  return (
    <section className="border-4 border-slate-700 bg-slate-950/76 p-5">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="pixel-title text-2xl font-bold text-amber-300">职业路线图</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            {playbook.premise} 路线图把任务、技能和作品集串起来，帮助你看到下一步该练什么。
          </p>
        </div>
        <PixelBadge variant="warning">{progress}%</PixelBadge>
      </div>
      <PixelProgress value={progress} color="#f59e0b" />

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage, index) => {
          const current = index === Math.min(completedMissionCount, stages.length - 1);
          const done = index < completedMissionCount;
          return (
            <article
              key={stage.name}
              className={`border-2 p-4 ${
                done
                  ? 'border-emerald-500 bg-emerald-950/25'
                  : current
                    ? 'border-amber-500 bg-amber-950/25'
                    : 'border-slate-700 bg-slate-900/55'
              }`}
            >
              <p className="font-mono text-xs text-slate-500">Stage 0{index + 1}</p>
              <h3 className="mt-2 font-bold text-amber-300">{stage.name}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">{stage.description}</p>
              <div className="mt-4 border border-slate-700 bg-slate-950/45 p-2 text-xs leading-5 text-slate-300">
                练习：{stage.practice}
              </div>
              <div className="mt-2 border border-slate-700 bg-slate-950/45 p-2 text-xs text-slate-300">
                奖励：{stage.reward}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
