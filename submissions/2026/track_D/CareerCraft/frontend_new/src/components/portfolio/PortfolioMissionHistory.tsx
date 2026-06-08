import React from 'react';
import { useRouter } from 'next/navigation';
import { EmptyState } from '@/components/common';
import { PixelBadge, PixelButton } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { MissionStatus } from '@/types';

interface MissionHistoryItem {
  id: string;
  title: string;
  careerId: string;
  status: MissionStatus;
  rewardExp: number;
  hasFeedback: boolean;
}

interface PortfolioMissionHistoryProps {
  missions: MissionHistoryItem[];
}

export default function PortfolioMissionHistory({ missions }: PortfolioMissionHistoryProps) {
  const router = useRouter();

  if (missions.length === 0) {
    return (
      <div>
        <h2 className="pixel-title mb-3 text-xl font-bold text-amber-300">任务历史</h2>
        <EmptyState description="还没有任务记录，去职业大厅开启第一段职业模拟吧。" />
      </div>
    );
  }

  return (
    <div>
      <h2 className="pixel-title mb-3 text-xl font-bold text-amber-300">任务历史</h2>
      <div className="space-y-2">
        {missions.map((mission) => (
          <div
            key={mission.id}
            className="border-2 border-slate-700 bg-slate-950 p-3 transition-colors hover:border-amber-600"
          >
            <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
              <div className="flex-1">
                <h4 className="mb-2 text-sm font-bold text-slate-100">{mission.title}</h4>
                <div className="flex flex-wrap items-center gap-2">
                  <PixelBadge variant="neutral" className="px-1.5 py-0 text-xs">
                    {getCareerName(mission.careerId)}
                  </PixelBadge>
                  <span className={`border-2 px-1.5 py-0.5 text-xs font-bold ${getStatusColor(mission.status)}`}>
                    {getStatusText(mission.status)}
                  </span>
                  <span className="text-xs font-bold text-emerald-400">+{mission.rewardExp} XP</span>
                </div>
              </div>

              {mission.status === MissionStatus.COMPLETED && mission.hasFeedback ? (
                <PixelButton
                  variant="secondary"
                  onClick={() => router.push(ROUTES.MISSION_FEEDBACK(mission.id))}
                  className="w-full py-1 text-xs md:w-auto"
                >
                  查看报告
                </PixelButton>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getStatusColor(status: MissionStatus) {
  switch (status) {
    case MissionStatus.COMPLETED:
      return 'border-emerald-700 bg-emerald-950/40 text-emerald-300';
    case MissionStatus.SUBMITTED:
      return 'border-amber-700 bg-amber-950/40 text-amber-300';
    case MissionStatus.ACCEPTED:
      return 'border-amber-700 bg-amber-950/40 text-amber-300';
    default:
      return 'border-slate-700 bg-slate-900 text-slate-400';
  }
}

function getStatusText(status: MissionStatus) {
  switch (status) {
    case MissionStatus.COMPLETED:
      return '已完成';
    case MissionStatus.SUBMITTED:
      return '已提交';
    case MissionStatus.ACCEPTED:
      return '进行中';
    default:
      return '未知';
  }
}

function getCareerName(careerId: string) {
  switch (careerId) {
    case 'software-engineer':
      return '软件工程';
    case 'data-analyst':
      return '数据分析';
    case 'product-designer':
      return '产品设计';
    case 'ai-researcher':
      return 'AI 研究';
    default:
      return '多职业';
  }
}
