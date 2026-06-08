import { ROUTES } from '@/constants';
import { missions } from '@/data/missions';
import { MVP_MISSION_ID } from '@/utils/demoFlow';

export function getCareerRouteByMissionId(missionId: string): string {
  for (const careerMissions of Object.values(missions)) {
    const mission = careerMissions.find(m => m.id === missionId);
    if (mission && mission.careerId) {
      return ROUTES.CAREER(mission.careerId);
    }
  }
  return ROUTES.LOBBY;
}

export function getMissionSubmitRoute(missionId: string): string {
  return ROUTES.MISSION_SUBMIT(missionId);
}

export function getMissionFeedbackRoute(missionId: string): string {
  return ROUTES.MISSION_FEEDBACK(missionId);
}

/**
 * 判断是否是 MVP 演示任务
 */
export function isMvpMission(missionId: string): boolean {
  return (
    missionId === MVP_MISSION_ID || 
    missionId.includes('mvp') || 
    missionId.includes('da-mvp') ||
    missionId.includes('da-') ||
    missionId.includes('data-analyst')
  );
}
