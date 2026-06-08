import React from 'react';
import { useRouter } from 'next/navigation';
import { PixelBadge, PixelButton } from '@/components/pixel';
import { Mission, MissionStatus } from '@/types';
import { ROUTES } from '@/constants';

interface MissionKanbanCardProps {
  mission: Mission;
  currentStatus: MissionStatus;
  onCardClick: () => void;
  onButtonClick: () => void;
  isMvp?: boolean;
}

export default function MissionKanbanCard({
  mission,
  currentStatus,
  onCardClick,
  onButtonClick,
  isMvp = false
}: MissionKanbanCardProps) {
  const router = useRouter();
  const isLocked = currentStatus === MissionStatus.LOCKED;
  
  const goToDetail = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(ROUTES.MISSION(mission.id));
  };
  
  function getDifficultyBadge(difficulty: string) {
    switch (difficulty) {
      case 'easy': return { variant: 'fun' as const, text: '⭐ 简单' };
      case 'medium': return { variant: 'honor' as const, text: '⭐⭐ 中等' };
      case 'hard': return { variant: 'warning' as const, text: '⭐⭐⭐ 困难' };
      default: return { variant: 'neutral' as const, text: '未知' };
    }
  }

  function getStatusBadge(status: MissionStatus) {
    switch (status) {
      case MissionStatus.LOCKED: return { variant: 'neutral' as const, text: '🔒 未解锁' };
      case MissionStatus.AVAILABLE: return { variant: 'fun' as const, text: '✨ 可接受' };
      case MissionStatus.ACCEPTED: return { variant: 'honor' as const, text: '📝 进行中' };
      case MissionStatus.SUBMITTED: return { variant: 'neutral' as const, text: '⏳ 评审中' };
      case MissionStatus.COMPLETED: return { variant: 'honor' as const, text: '✅ 已完成' };
      default: return { variant: 'neutral' as const, text: '未知' };
    }
  }

  function getButtonText(status: MissionStatus) {
    switch (status) {
      case MissionStatus.LOCKED: return '🔒 未解锁';
      case MissionStatus.AVAILABLE: return '✅ 接受任务';
      case MissionStatus.ACCEPTED: return '📝 继续任务';
      case MissionStatus.SUBMITTED: return '📋 查看反馈';
      case MissionStatus.COMPLETED: return '📋 查看报告';
      default: return '查看';
    }
  }

  function getStatusColor(status: MissionStatus) {
    switch (status) {
      case MissionStatus.LOCKED: return '#64748b';
      case MissionStatus.AVAILABLE: return '#10b981';
      case MissionStatus.ACCEPTED: return '#3b82f6';
      case MissionStatus.SUBMITTED: return '#f59e0b';
      case MissionStatus.COMPLETED: return '#8b5cf6';
      default: return '#64748b';
    }
  }

  const difficultyBadge = getDifficultyBadge(mission.difficulty);
  const statusBadge = getStatusBadge(currentStatus);
  const statusColor = isMvp ? '#6366f1' : getStatusColor(currentStatus);

  return (
    <div
      className={`
        relative p-3 border-2 transition-all duration-150
        ${isLocked ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:-translate-y-1'}
        ${isMvp ? 'animate-pulse' : ''}
      `}
      style={{
        backgroundColor: isMvp ? 'rgba(99, 102, 241, 0.15)' : '#1e293b',
        borderColor: isMvp ? '#6366f1' : statusColor,
        borderWidth: isMvp ? '3px' : '2px',
        boxShadow: isMvp 
          ? '0 0 20px rgba(99, 102, 241, 0.3), inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #4338ca' 
          : 'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #334155',
      }}
      onClick={onCardClick}
    >
      {/* MVP 标记 */}
      {isMvp && (
        <div className="absolute -top-2 -right-2">
          <PixelBadge variant="primary" className="text-xs">
            🎯 主线任务
          </PixelBadge>
        </div>
      )}
      
      {/* 任务标题和状态 */}
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-sm font-bold" style={{ color: statusColor }}>
          {mission.title}
        </h3>
        <PixelBadge variant={statusBadge.variant} className="text-xs">
          {statusBadge.text}
        </PixelBadge>
      </div>

      {/* 简短描述 */}
      <p className="text-slate-400 text-xs mb-2 line-clamp-2">
        {mission.description}
      </p>

      {/* 徽章区域 */}
      <div className="flex flex-wrap gap-1 mb-2">
        {isMvp && (
          <PixelBadge variant="primary" className="text-xs">
            🚀 MVP 任务
          </PixelBadge>
        )}
        <PixelBadge variant={difficultyBadge.variant} className="text-xs">
          {difficultyBadge.text}
        </PixelBadge>
        <PixelBadge variant="neutral" className="text-xs">
          +{mission.rewardExp} XP
        </PixelBadge>
      </div>

      {/* 操作按钮 */}
      <PixelButton
        variant={currentStatus === MissionStatus.AVAILABLE ? 'primary' : 'secondary'}
        onClick={onButtonClick}
        disabled={isLocked}
        className="w-full text-xs"
      >
        {getButtonText(currentStatus)}
      </PixelButton>
      
      {/* 查看详情按钮 */}
      {!isLocked && (
        <button
          onClick={goToDetail}
          className="w-full text-xs text-slate-400 hover:text-amber-400 transition-colors mt-1 text-center py-1"
        >
          → 查看详情
        </button>
      )}
    </div>
  );
}
