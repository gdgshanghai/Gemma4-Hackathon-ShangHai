import React from 'react';
import { EmptyState } from '@/components/common';

interface Badge {
  id: string;
  name: string;
  icon: string;
  description: string;
  earned: boolean;
}

interface PortfolioBadgesProps {
  badges: Badge[];
}

export default function PortfolioBadges({ badges }: PortfolioBadgesProps) {
  const earnedBadges = badges.filter(b => b.earned);

  if (earnedBadges.length === 0) {
    return (
      <div>
        <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
          <span>🏆</span>
          <span>徽章墙</span>
        </h2>
        <EmptyState 
          description="完成任务后会在这里点亮徽章。"
        />
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
        <span>🏆</span>
        <span>徽章墙</span>
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {badges.map((badge) => (
          <div 
            key={badge.id}
            className={`relative p-3 border-4 text-center transition-all duration-300 transform ${
              badge.earned 
                ? 'bg-gradient-to-b from-amber-800/50 to-amber-950/70 border-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.4)] hover:scale-105 hover:shadow-[0_0_30px_rgba(245,158,11,0.6)]' 
                : 'bg-slate-900/50 border-slate-700 opacity-50 grayscale'
            }`}
          >
            <div className={`text-5xl mb-2 ${badge.earned ? 'animate-bounce' : ''}`}>{badge.icon}</div>
            <div className={`font-bold text-sm mb-1 ${badge.earned ? 'text-amber-300' : 'text-slate-500'}`}>{badge.name}</div>
            <div className={`text-xs leading-tight ${badge.earned ? 'text-slate-300' : 'text-slate-600'}`}>{badge.description}</div>
            {!badge.earned && (
              <div className="mt-2">
                <span className="text-xs text-slate-600 border-2 border-slate-700 px-2 py-0.5">🔒 未解锁</span>
              </div>
            )}
            {badge.earned && (
              <div className="absolute -top-1 -right-1 text-xl">✨</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
