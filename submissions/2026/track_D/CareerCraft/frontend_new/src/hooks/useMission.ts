'use client';

import { useCallback } from 'react';
import { missionService } from '@/services';
import { Mission } from '@/types';
import { useAsyncTask } from './useAsyncTask';

export function useMission() {
  const listTask = useAsyncTask<Mission[]>();
  const activeTask = useAsyncTask<Mission>();
  const {
    data: missionsData,
    error: listError,
    loading: listLoading,
    run: runListTask,
  } = listTask;
  const {
    data: missionData,
    error: activeError,
    loading: activeLoading,
    run: runActiveTask,
  } = activeTask;

  const loadMissions = useCallback(async () => {
    return runListTask(() => missionService.getMissions());
  }, [runListTask]);

  const loadMission = useCallback(
    async (missionId: string) => {
      return runActiveTask(async () => {
        const mission = await missionService.getMissionById(missionId);
        if (!mission) throw new Error(`Mission not found: ${missionId}`);
        return mission;
      });
    },
    [runActiveTask]
  );

  const generateMission = useCallback(
    async (
      roleId: string,
      difficulty = 'easy',
      taskDirection?: string | null,
      missionStyle?: string | null,
    ) => {
      return runActiveTask(() =>
        missionService.generateMission(roleId, difficulty, taskDirection, missionStyle)
      );
    },
    [runActiveTask]
  );

  return {
    missions: missionsData ?? [],
    mission: missionData,
    loading: listLoading || activeLoading,
    error: listError ?? activeError,
    loadMissions,
    loadMission,
    generateMission,
  };
}
