import React from 'react';
import { PixelProgress } from '@/components/pixel';
import { SkillNode } from '@/types';

export type SkillNodeStatus = 'locked' | 'available' | 'learning' | 'mastered';

interface SkillNodeCardProps {
  skill: SkillNode;
  onClick: () => void;
}

export function getSkillStatus(skill: SkillNode): SkillNodeStatus {
  const unlocked = skill.unlocked ?? false;
  const level = skill.level ?? 0;
  const maxLevel = skill.maxLevel ?? 1;
  
  if (!unlocked) return 'locked';
  if (level >= maxLevel) return 'mastered';
  if (level > 0) return 'learning';
  return 'available';
}

function getStatusColor(status: SkillNodeStatus) {
  switch (status) {
    case 'locked': return '#475569';
    case 'available': return '#3b82f6';
    case 'learning': return '#f59e0b';
    case 'mastered': return '#10b981';
    default: return '#475569';
  }
}

function getStatusBorder(status: SkillNodeStatus) {
  switch (status) {
    case 'locked': return '#475569';
    case 'available': return '#3b82f6';
    case 'learning': return '#f59e0b';
    case 'mastered': return '#10b981';
    default: return '#475569';
  }
}

function getStatusIcon(status: SkillNodeStatus) {
  switch (status) {
    case 'locked': return '🔒';
    case 'available': return '📖';
    case 'learning': return '⭐';
    case 'mastered': return '✨';
    default: return '🔒';
  }
}

export default function SkillNodeCard({ skill, onClick }: SkillNodeCardProps) {
  const status = getSkillStatus(skill);
  const color = getStatusColor(status);
  const borderColor = getStatusBorder(status);
  const icon = getStatusIcon(status);
  const progress = status !== 'locked' && skill.expToNext > 0
    ? Math.min(100, Math.round((skill.exp / skill.expToNext) * 100))
    : 0;

  return (
    <div
      onClick={onClick}
      className={`
        relative p-4 bg-slate-800 border-4 cursor-pointer transition-all duration-150
        ${status === 'locked' ? 'opacity-60' : ''}
        hover:transform hover:-translate-y-1
      `}
      style={{
        borderColor,
        boxShadow: 'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #334155',
      }}
    >
      {/* 顶部图标 */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <div className="text-xs font-bold" style={{ color }}>
          Lv.{skill.level}/{skill.maxLevel}
        </div>
      </div>

      {/* 技能名称 */}
      <h3 
        className="text-sm font-bold mb-2 truncate"
        style={{ color }}
      >
        {skill.name}
      </h3>

      {/* 进度条（只在非锁定状态显示） */}
      {status !== 'locked' && (
        <div className="mt-2">
          <PixelProgress 
            value={progress}
            color={status === 'mastered' ? '#10b981' : status === 'learning' ? '#f59e0b' : '#3b82f6'}
            height="h-2"
          />
        </div>
      )}

      {/* 锁定状态提示 */}
      {status === 'locked' && (
        <div className="mt-2 text-xs text-slate-500">
          🔒 需要解锁
        </div>
      )}

      {/* 精通状态星标 */}
      {status === 'mastered' && (
        <div className="absolute -top-2 -right-2 text-xl">
          ⭐
        </div>
      )}
    </div>
  );
}
