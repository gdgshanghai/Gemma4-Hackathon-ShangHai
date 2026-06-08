import React from 'react';
import { PixelProgress } from '@/components/pixel';

interface PortfolioStatsProps {
  totalXP: number;
  completedMissions: number;
  submittedMissions: number;
  unlockedSkills: number;
  completionRate: number;
}

export default function PortfolioStats({
  totalXP,
  completedMissions,
  submittedMissions,
  unlockedSkills,
  completionRate
}: PortfolioStatsProps) {
  const stats = [
    { label: '总 XP', value: totalXP, icon: '⚡', color: '#10b981' },
    { label: '已完成任务', value: completedMissions, icon: '✅', color: '#3b82f6' },
    { label: '已提交任务', value: submittedMissions, icon: '📤', color: '#8b5cf6' },
    { label: '已解锁技能', value: unlockedSkills, icon: '🎯', color: '#f59e0b' }
  ];

  return (
    <div>
      <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
        <span>📊</span>
        <span>成长统计</span>
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {stats.map((stat, index) => (
          <div 
            key={index}
            className="p-3 bg-slate-800 border-3 border-slate-700 text-center hover:border-amber-600 transition-colors"
          >
            <div className="text-2xl mb-1">{stat.icon}</div>
            <div className="text-xl font-bold" style={{ color: stat.color }}>
              {stat.value}
            </div>
            <div className="text-xs text-slate-400 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>
      
      <div className="bg-slate-800 border-3 border-slate-700 p-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-slate-300 font-medium">整体成长进度</span>
          <span className="text-amber-500 font-bold">{completionRate}%</span>
        </div>
        <PixelProgress value={completionRate} color="#f59e0b" />
      </div>
    </div>
  );
}
