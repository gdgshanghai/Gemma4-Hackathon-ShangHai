import React from 'react';
import { PixelCard } from '@/components/pixel';
import MissionKanbanCard from './MissionKanbanCard';
import { Mission, MissionStatus } from '@/types';

interface MissionKanbanColumnProps {
  title: string;
  icon: string;
  status: MissionStatus;
  missions: { mission: Mission; currentStatus: MissionStatus }[];
  onCardClick: (mission: Mission) => void;
  onButtonClick: (mission: Mission, currentStatus: MissionStatus) => void;
  emptyText?: string;
  isMvpMission?: (mission: Mission) => boolean;
}

export default function MissionKanbanColumn({
  title,
  icon,
  status,
  missions,
  onCardClick,
  onButtonClick,
  emptyText = "暂无任务",
  isMvpMission = () => false
}: MissionKanbanColumnProps) {
  return (
    <div className="min-w-0">
      <PixelCard className="h-full">
        {/* 列标题 */}
        <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-slate-700">
          <span className="text-lg">{icon}</span>
          <h3 className="font-bold text-slate-300 text-sm">
            {title}
          </h3>
          <span className="ml-auto text-xs bg-slate-800 px-2 py-1 text-slate-400">
            {missions.length}
          </span>
        </div>

        {/* 任务列表 */}
        <div className="space-y-2 overflow-y-auto pr-1" style={{ maxHeight: '400px' }}>
          {missions.length === 0 ? (
            <div className="py-6 text-center">
              <p className="text-slate-500 text-xs">
                {emptyText}
              </p>
            </div>
          ) : (
            missions.map(({ mission, currentStatus }) => (
              <MissionKanbanCard
                key={mission.id}
                mission={mission}
                currentStatus={currentStatus}
                onCardClick={() => onCardClick(mission)}
                onButtonClick={() => onButtonClick(mission, currentStatus)}
                isMvp={isMvpMission(mission)}
              />
            ))
          )}
        </div>
      </PixelCard>
    </div>
  );
}
