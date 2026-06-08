import React from 'react';
import { PixelProgress, PixelBadge } from '@/components/pixel';

export type StageStatus = 'locked' | 'upcoming' | 'current' | 'completed';

interface CareerStageCardProps {
  stageNumber: number;
  stageName: string;
  description: string;
  status: StageStatus;
  recommendedMissions: number;
  completedMissions: number;
  reward: string;
  onClick: () => void;
}

export default function CareerStageCard({
  stageNumber,
  stageName,
  description,
  status,
  recommendedMissions,
  completedMissions,
  reward,
  onClick
}: CareerStageCardProps) {
  const getStatusColors = () => {
    switch (status) {
      case 'locked':
        return {
          border: 'border-slate-600',
          bg: 'bg-slate-800',
          text: 'text-slate-400',
          headerBg: 'bg-slate-700'
        };
      case 'upcoming':
        return {
          border: 'border-slate-500',
          bg: 'bg-slate-800',
          text: 'text-slate-300',
          headerBg: 'bg-slate-700'
        };
      case 'current':
        return {
          border: 'border-amber-500',
          bg: 'bg-slate-800',
          text: 'text-slate-200',
          headerBg: 'bg-amber-900/50'
        };
      case 'completed':
        return {
          border: 'border-green-500',
          bg: 'bg-green-900/20',
          text: 'text-slate-200',
          headerBg: 'bg-green-800/50'
        };
    }
  };

  const colors = getStatusColors();
  const progress = recommendedMissions > 0 ? (completedMissions / recommendedMissions) * 100 : 0;

  return (
    <div
      className={`cursor-pointer transition-all duration-200 hover:scale-[1.02] ${status === 'locked' ? 'cursor-not-allowed opacity-60' : ''}`}
      onClick={onClick}
    >
      <div className={`${colors.bg} border-4 ${colors.border} p-4`}>
        {/* 阶段头部 */}
        <div className={`${colors.headerBg} -mx-4 -mt-4 mb-4 px-4 py-2 border-b-4 ${colors.border}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {status === 'locked' ? (
                <span className="text-2xl">🔒</span>
              ) : status === 'completed' ? (
                <span className="text-2xl">✅</span>
              ) : (
                <span className="text-2xl">{stageNumber === 1 ? '1️⃣' : stageNumber === 2 ? '2️⃣' : stageNumber === 3 ? '3️⃣' : '4️⃣'}</span>
              )}
              <h3 className={`font-bold text-lg ${colors.text}`}>{stageName}</h3>
            </div>
            {status === 'current' && (
              <PixelBadge variant="warning">进行中</PixelBadge>
            )}
            {status === 'completed' && (
              <PixelBadge variant="success">已完成</PixelBadge>
            )}
          </div>
        </div>

        {/* 阶段说明 */}
        <p className={`text-sm ${colors.text} mb-4`}>{description}</p>

        {/* 任务进度 */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-2">
            <span className={colors.text}>任务进度</span>
            <span className={colors.text}>{completedMissions} / {recommendedMissions}</span>
          </div>
          {status !== 'locked' && (
            <PixelProgress 
              value={progress} 
              color={status === 'completed' ? '#22c55e' : '#f59e0b'} 
            />
          )}
        </div>

        {/* 阶段奖励 */}
        <div className={`p-2 bg-slate-700/50 border-2 ${colors.border}`}>
          <div className="flex items-center gap-2">
            <span className="text-lg">🏆</span>
            <span className={`text-sm ${colors.text}`}>{reward}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
