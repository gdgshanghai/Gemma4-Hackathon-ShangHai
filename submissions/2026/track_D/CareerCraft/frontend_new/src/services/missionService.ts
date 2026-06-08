import { careerPlaybooks, mergeCareerMissions, missions } from '@/data';
import { MVP_MISSION } from '@/data/mvpMission';
import { Mission } from '@/types';
import { AbortError, api, EvaluationResult, GeneratedMission } from './apiClient';
import {
  CAREER_API_CONFIGS,
  mapBackendMissionToMission,
  toMissionRoleId,
} from './apiAdapters';

export const EVALUATION_CACHE_PREFIX = 'careercraft-evaluation-';
export type MissionDataSource = 'api' | 'fallback';
export interface MissionWithSource {
  mission: Mission;
  source: MissionDataSource;
}

function getAllFallbackMissions(): Mission[] {
  return Object.keys(careerPlaybooks).flatMap((careerId) =>
    mergeCareerMissions(careerId, missions[careerId] || []),
  );
}

function mergeMissionLists(primary: Mission[], fallback: Mission[]): Mission[] {
  const seen = new Set(primary.map((mission) => mission.id));
  return [...primary, ...fallback.filter((mission) => !seen.has(mission.id))];
}

function mapToMission(generated: GeneratedMission, careerId: string): Mission {
  const mission = mapBackendMissionToMission(
    {
      ...generated,
      status: generated.status || 'active',
      feedback: null,
      feynman_active: false,
    },
    careerId,
  );
  if (!mission) {
    throw new Error('Generated mission could not be mapped to a frontend mission.');
  }
  return mission;
}

export function cacheEvaluationResult(missionId: string, result: EvaluationResult) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(`${EVALUATION_CACHE_PREFIX}${missionId}`, JSON.stringify(result));
}

export function getCachedEvaluationResult(missionId: string): EvaluationResult | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(`${EVALUATION_CACHE_PREFIX}${missionId}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as EvaluationResult;
  } catch {
    return null;
  }
}

export const missionService = {
  getMissions: async (): Promise<Mission[]> => {
    try {
      const profile = await api.fetchUserProfile();
      const backendMissions = profile.missions
        .map((m) => mapBackendMissionToMission(m, profile.user.current_career_id))
        .filter((mission): mission is Mission => Boolean(mission));
      return mergeMissionLists(backendMissions, getAllFallbackMissions());
    } catch (err) {
      if (err instanceof AbortError) throw err;
      console.warn('Mission list API failed; using local fallback data.', err);
      return getAllFallbackMissions();
    }
  },

  getMissionsByCareerId: async (careerId: string): Promise<Mission[]> => {
    const fallback = careerId === 'data-analyst'
      ? [
          MVP_MISSION,
          ...(missions[careerId] || []).filter((mission) => mission.id !== MVP_MISSION.id),
        ]
      : missions[careerId] || [];

    try {
      const allMissions = await missionService.getMissions();
      const filtered = allMissions.filter((m) => m.careerId === careerId);
      return mergeCareerMissions(careerId, mergeMissionLists(filtered, fallback));
    } catch (err) {
      if (err instanceof AbortError) throw err;
      return mergeCareerMissions(careerId, fallback);
    }
  },

  getMissionById: async (missionId: string): Promise<Mission | undefined> => {
    if (missionId === MVP_MISSION.id) {
      return MVP_MISSION;
    }

    try {
      const profile = await api.fetchUserProfile();
      const backendMission = profile.missions.find((m) => m.mission_id === missionId);
      if (backendMission) {
        const mission = mapBackendMissionToMission(
          backendMission,
          profile.user.current_career_id,
          { includeFailedAsLocked: true },
        );
        if (mission) return mission;
      }

      const allMissions = await missionService.getMissions();
      const mission = allMissions.find((m) => m.id === missionId);
      if (mission) return mission;
    } catch (err) {
      if (err instanceof AbortError) throw err;
    }

    for (const careerMissions of Object.values(missions)) {
      const mission = careerMissions.find((m) => m.id === missionId);
      if (mission) return mission;
    }
    for (const playbook of Object.values(careerPlaybooks)) {
      const mission = playbook.bridgeMissions.find((item) => item.id === missionId);
      if (mission) return mission;
    }
    return undefined;
  },

  generateMission: async (
    careerId: string,
    difficulty: string = 'easy',
    taskDirection?: string | null,
    missionStyle?: string | null,
  ): Promise<Mission> => {
    const { mission } = await missionService.generateMissionWithSource(
      careerId,
      difficulty,
      taskDirection,
      missionStyle,
    );
    return mission;
  },

  generateMissionWithSource: async (
    careerId: string,
    difficulty: string = 'easy',
    taskDirection?: string | null,
    missionStyle?: string | null,
  ): Promise<MissionWithSource> => {
    const roleId = toMissionRoleId(careerId);
    if (roleId === careerId && CAREER_API_CONFIGS[careerId]?.apiSupported === false) {
      throw new Error('This career does not support API mission generation yet.');
    }
    const generated = await api.generateMission(roleId, difficulty, taskDirection, missionStyle);
    return { mission: mapToMission(generated, careerId), source: 'api' };
  },

  evaluateSubmission: async (missionId: string, submissionText: string): Promise<EvaluationResult> => {
    const result = await api.evaluateSubmission(missionId, submissionText);
    cacheEvaluationResult(missionId, result);
    return result;
  },
};
