import React from 'react';
import { PixelBadge } from '@/components/pixel';

interface PortfolioHeaderProps {
  userName: string;
  currentDirection: string;
  totalXP: number;
  completedMissions: number;
  badgesCount: number;
  level: number;
}

export default function PortfolioHeader({
  userName,
  currentDirection,
  totalXP,
  completedMissions,
  badgesCount,
  level
}: PortfolioHeaderProps) {
  return (
    <div>
      <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
        <div className="w-20 h-20 bg-gradient-to-br from-amber-500 to-orange-600 border-4 border-amber-400 flex items-center justify-center flex-shrink-0 shadow-[0_0_15px_rgba(245,158,11,0.4)]">
          <span className="text-4xl">👤</span>
        </div>
        
        <div className="flex-1 space-y-2">
          <div>
            <h1 className="text-2xl font-bold text-amber-500">{userName}</h1>
            <p className="text-slate-400 text-sm mt-0.5">{currentDirection}</p>
          </div>
          
          <div className="flex flex-wrap gap-2">
            <PixelBadge variant="honor" className="py-0.5">
              等级 {level}
            </PixelBadge>
            <PixelBadge variant="fun" className="py-0.5">
              {totalXP} XP
            </PixelBadge>
            <PixelBadge variant="warning" className="py-0.5">
              已完成 {completedMissions} 任务
            </PixelBadge>
            <PixelBadge variant="neutral" className="py-0.5">
              {badgesCount} 徽章
            </PixelBadge>
          </div>
        </div>
      </div>
    </div>
  );
}
