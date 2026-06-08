'use client';

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '@/constants';
import { MissionStatus } from '@/types';

interface MissionDraft {
  report: string;
  code: string;
}

interface MissionStore {
  missionStatuses: Record<string, MissionStatus>;
  missionDrafts: Record<string, MissionDraft>;

  acceptMission: (missionId: string) => void;
  saveDraft: (missionId: string, draft: MissionDraft) => void;
  submitMission: (missionId: string) => void;
  completeMission: (missionId: string) => void;
  resetMissionStatuses: () => void;

  getMissionStatus: (missionId: string, defaultStatus: MissionStatus) => MissionStatus;
  getDraft: (missionId: string) => MissionDraft | null;
}

function normalizeStoredStatus(status: MissionStatus | string | undefined, fallback: MissionStatus): MissionStatus {
  if (Object.values(MissionStatus).includes(status as MissionStatus)) {
    return status as MissionStatus;
  }
  if (status === 'active') return MissionStatus.ACCEPTED;
  if (status === 'failed') return MissionStatus.LOCKED;
  return fallback;
}

export const useMissionStore = create<MissionStore>()(
  persist(
    (set, get) => ({
      missionStatuses: {},
      missionDrafts: {},

      acceptMission: (missionId) =>
        set((state) => ({
          missionStatuses: {
            ...state.missionStatuses,
            [missionId]: MissionStatus.ACCEPTED,
          },
        })),

      saveDraft: (missionId, draft) =>
        set((state) => ({
          missionDrafts: {
            ...state.missionDrafts,
            [missionId]: draft,
          },
        })),

      submitMission: (missionId) =>
        set((state) => ({
          missionStatuses: {
            ...state.missionStatuses,
            [missionId]: MissionStatus.SUBMITTED,
          },
        })),

      completeMission: (missionId) =>
        set((state) => ({
          missionStatuses: {
            ...state.missionStatuses,
            [missionId]: MissionStatus.COMPLETED,
          },
        })),

      resetMissionStatuses: () =>
        set(() => ({
          missionStatuses: {},
          missionDrafts: {},
        })),

      getMissionStatus: (missionId, defaultStatus) => {
        const state = get();
        return normalizeStoredStatus(state.missionStatuses[missionId], defaultStatus);
      },

      getDraft: (missionId) => {
        const state = get();
        return state.missionDrafts[missionId] || null;
      },
    }),
    {
      name: STORAGE_KEYS.MISSION_STATUSES,
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
