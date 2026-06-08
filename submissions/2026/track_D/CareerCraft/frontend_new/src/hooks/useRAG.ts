'use client';

import { useCallback } from 'react';
import { resourceService } from '@/services';
import { Resource } from '@/types';
import { useAsyncTask } from './useAsyncTask';

export function useRAG() {
  const task = useAsyncTask<Resource[]>();
  const { cancel, data, error, loading, run, setData } = task;

  const search = useCallback(
    async (query: string, careerId: string) => {
      const trimmed = query.trim();
      if (!trimmed) {
        setData([]);
        return [];
      }
      return run(() => resourceService.searchResources(trimmed, careerId));
    },
    [run, setData]
  );

  return {
    resources: data ?? [],
    loading,
    error,
    search,
    cancel,
  };
}
