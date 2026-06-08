import React from 'react';
import { useRouter } from 'next/navigation';
import { PixelCard, PixelButton } from '@/components/pixel';
import { Mission, MissionStatus } from '@/types';
import { useMissionStore } from '@/stores/missionStore';
import { ROUTES } from '@/constants';

interface MissionActionPanelProps {
  mission: Mission;
}

export default function MissionActionPanel({ mission }: MissionActionPanelProps) {
  const router = useRouter();
  const { getMissionStatus, acceptMission } = useMissionStore();
  const currentStatus = getMissionStatus(mission.id, mission.status);
  
  function getButtonConfig() {
    switch (currentStatus) {
      case MissionStatus.LOCKED:
        return {
          label: '🔒 任务未解锁',
          disabled: true,
          variant: 'secondary' as const
        };
      case MissionStatus.AVAILABLE:
        return {
          label: '✅ 接受任务',
          disabled: false,
          variant: 'primary' as const
        };
      case MissionStatus.ACCEPTED:
        return {
          label: '📝 继续提交',
          disabled: false,
          variant: 'primary' as const
        };
      case MissionStatus.SUBMITTED:
        return {
          label: '📋 查看评审',
          disabled: false,
          variant: 'secondary' as const
        };
      case MissionStatus.COMPLETED:
        return {
          label: '📋 查看报告',
          disabled: false,
          variant: 'secondary' as const
        };
      default:
        return {
          label: '查看任务',
          disabled: true,
          variant: 'secondary' as const
        };
    }
  }
  
  const handleButtonClick = () => {
    switch (currentStatus) {
      case MissionStatus.AVAILABLE:
        acceptMission(mission.id);
        router.push(ROUTES.MISSION_SUBMIT(mission.id));
        break;
      case MissionStatus.ACCEPTED:
        router.push(ROUTES.MISSION_SUBMIT(mission.id));
        break;
      case MissionStatus.SUBMITTED:
      case MissionStatus.COMPLETED:
        router.push(ROUTES.MISSION_FEEDBACK(mission.id));
        break;
    }
  };
  
  const buttonConfig = getButtonConfig();
  
  return (
    <PixelCard title="⚡ 任务操作">
      <div className="space-y-4">
        {/* 状态说明 */}
        <div className="bg-slate-800 p-3 border-2 border-slate-700 text-center">
          <p className="text-slate-300 text-sm">
            {currentStatus === MissionStatus.LOCKED && '请完成前置任务解锁此任务'}
            {currentStatus === MissionStatus.AVAILABLE && '准备好挑战新任务了吗？'}
            {currentStatus === MissionStatus.ACCEPTED && '继续完善你的解决方案'}
            {currentStatus === MissionStatus.SUBMITTED && '查看 AI导师的专业评审'}
            {currentStatus === MissionStatus.COMPLETED && '恭喜！任务已完成'}
          </p>
        </div>
        
        {/* 操作按钮 */}
        <PixelButton
          variant={buttonConfig.variant}
          onClick={handleButtonClick}
          disabled={buttonConfig.disabled}
          className="w-full"
        >
          {buttonConfig.label}
        </PixelButton>
      </div>
    </PixelCard>
  );
}
