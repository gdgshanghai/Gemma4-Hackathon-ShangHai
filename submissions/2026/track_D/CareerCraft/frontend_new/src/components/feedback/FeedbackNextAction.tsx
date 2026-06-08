import React from 'react';
import { PixelButton, PixelCard } from '@/components/pixel';

interface FeedbackNextActionProps {
  hasAvailableTasks: boolean;
  allTasksCompleted: boolean;
  onBackToHub: () => void;
  onNextMission: () => void;
  onBackToLobby: () => void;
}

export default function FeedbackNextAction({
  hasAvailableTasks,
  allTasksCompleted,
  onBackToHub,
  onNextMission,
  onBackToLobby,
}: FeedbackNextActionProps) {
  const message = allTasksCompleted
    ? '这一阶段的职业训练已经完成，可以回到大厅探索其他职业岛。'
    : hasAvailableTasks
      ? '继续接下一张任务卡，把刚得到的建议马上用起来。'
      : '当前职业暂无可接任务，可以先回到职业岛整理成长路线。';

  return (
    <PixelCard title="下一步">
      <div className="space-y-3">
        <div className="border-2 border-amber-700 bg-amber-950/25 p-3 text-sm leading-6 text-slate-200">
          {message}
        </div>

        {hasAvailableTasks && !allTasksCompleted ? (
          <PixelButton onClick={onNextMission} fullWidth>
            继续下一项任务
          </PixelButton>
        ) : null}

        <PixelButton variant="secondary" onClick={onBackToHub} fullWidth>
          返回职业岛
        </PixelButton>
        <PixelButton variant="secondary" onClick={onBackToLobby} fullWidth>
          返回职业大厅
        </PixelButton>
      </div>
    </PixelCard>
  );
}
