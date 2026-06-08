'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { careerService } from '@/services';
import { useUserStore } from '@/stores/userStore';
import { CareerIsland } from '@/types';
import { useAsyncTask } from './useAsyncTask';

export function useCareer(autoLoad = true) {
  const currentCareerId = useUserStore((state) => state.currentCareerId);
  const totalXp = useUserStore((state) => state.totalXp);
  const syncFromBackend = useUserStore((state) => state.syncFromBackend);
  const selectCareer = useUserStore((state) => state.selectCareer);
  const task = useAsyncTask<CareerIsland[]>();
  const { data, error, loading, run } = task;

  const refresh = useCallback(async () => {
    return run(async () => {
      const [careers] = await Promise.all([
        careerService.getAllCareerIslands(),
        syncFromBackend(),
      ]);
      return careers;
    });
  }, [run, syncFromBackend]);

  useEffect(() => {
    if (autoLoad) {
      refresh().catch(() => undefined);
    }
  }, [autoLoad, refresh]);

  const careers = useMemo(() => data ?? [], [data]);
  const activeCareer = useMemo(
    () => careers.find((career) => career.id === currentCareerId) ?? null,
    [careers, currentCareerId]
  );

  return {
    careers,
    activeCareer,
    currentCareerId,
    totalXp,
    loading,
    error,
    refresh,
    selectCareer,
  };
}
