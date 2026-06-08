'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { PixelCard, PixelBadge, PixelButton } from '@/components/pixel';
import { Mission, MissionStatus } from '@/types';
import { useMissionStore } from '@/stores/missionStore';
import { ROUTES } from '@/constants';

interface MentorGuidancePanelProps {
  missions: Mission[];
}

export default function MentorGuidancePanel({ missions }: MentorGuidancePanelProps) {
  const router = useRouter();
  const { getMissionStatus } = useMissionStore();

  // 处理任务状态
  const processedMissions = missions.map(mission => ({
    mission,
    currentStatus: getMissionStatus(mission.id, mission.status)
  }));

  // 按优先级筛选任务
  const acceptedMission = processedMissions.find(m => m.currentStatus === MissionStatus.ACCEPTED);
  const submittedMission = processedMissions.find(m => m.currentStatus === MissionStatus.SUBMITTED);
  const availableMission = processedMissions.find(m => m.currentStatus === MissionStatus.AVAILABLE);
  const completedMissions = processedMissions.filter(m => m.currentStatus === MissionStatus.COMPLETED);
  const lockedMissions = processedMissions.filter(m => m.currentStatus === MissionStatus.LOCKED);
  const visibleMissions = processedMissions.filter(m => m.currentStatus !== MissionStatus.LOCKED);

  // 确定当前场景
  let scenario: 'accepted' | 'submitted' | 'available' | 'all_completed' | 'locked_only';

  if (acceptedMission) {
    scenario = 'accepted';
  } else if (submittedMission) {
    scenario = 'submitted';
  } else if (availableMission) {
    scenario = 'available';
  } else if (completedMissions.length === visibleMissions.length && visibleMissions.length > 0) {
    scenario = 'all_completed';
  } else {
    scenario = 'locked_only';
  }

  // 获取对应的数据
  let title: string;
  let content: string;
  let buttonText: string;
  let buttonDisabled = false;
  let targetMission: Mission | null = null;

  switch (scenario) {
    case 'accepted':
      targetMission = acceptedMission!.mission;
      title = '继续推进任务';
      content = `你已经领取了任务「${targetMission.title}」，建议先补齐交付物，再提交给 AI 导师评审。`;
      buttonText = '继续任务';
      break;
    case 'submitted':
      targetMission = submittedMission!.mission;
      title = '查看评审结果';
      content = '你有任务正在评审中，可以查看 AI 导师给出的反馈。';
      buttonText = '查看反馈';
      break;
    case 'available':
      targetMission = availableMission!.mission;
      title = '推荐开始任务';
      content = `建议从「${targetMission.title}」开始，这是当前阶段最适合你的任务。`;
      buttonText = '查看任务';
      break;
    case 'all_completed':
      title = '阶段完成';
      content = '当前阶段任务已完成，可以继续解锁更高阶任务。';
      buttonText = '返回任务看板';
      break;
    case 'locked_only':
    default:
      title = '等待解锁';
      content = '完成前置任务后，新的挑战会自动解锁。';
      buttonText = '等待解锁';
      buttonDisabled = true;
  }

  // 处理按钮点击
  const handleButtonClick = () => {
    if (buttonDisabled) return;

    switch (scenario) {
      case 'accepted':
        if (targetMission) {
          router.push(ROUTES.MISSION_SUBMIT(targetMission.id));
        }
        break;
      case 'submitted':
        if (targetMission) {
          router.push(ROUTES.MISSION_FEEDBACK(targetMission.id));
        }
        break;
      case 'available':
      case 'all_completed':
        // 滚动到任务看板
        const taskBoard = document.getElementById('career-task-board');
        if (taskBoard) {
          taskBoard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        break;
    }
  };

  return (
    <PixelCard title="💡 导师建议">
      <div className="space-y-4">
        {/* 标题 */}
        <div className="flex items-center gap-2">
          <span className="text-lg">💡</span>
          <h4 className="font-bold text-amber-500">{title}</h4>
        </div>

        {/* 内容 */}
        <p className="text-slate-300 text-sm leading-relaxed">{content}</p>

        {/* 按钮 */}
        <PixelButton
          variant={scenario === 'accepted' ? 'primary' : 'secondary'}
          onClick={handleButtonClick}
          disabled={buttonDisabled}
          className="w-full"
        >
          {buttonText}
        </PixelButton>

        {/* 状态提示 */}
        <div className="flex flex-wrap gap-1 pt-2">
          {acceptedMission && <PixelBadge variant="honor">📝 进行中</PixelBadge>}
          {submittedMission && <PixelBadge variant="neutral">⏳ 评审中</PixelBadge>}
          {availableMission && <PixelBadge variant="fun">✨ 可接受</PixelBadge>}
          {!buttonDisabled && scenario === 'all_completed' && <PixelBadge variant="honor">🏆 已完成</PixelBadge>}
          {buttonDisabled && <PixelBadge variant="neutral">🔒 等待中</PixelBadge>}
        </div>
      </div>
    </PixelCard>
  );
}
