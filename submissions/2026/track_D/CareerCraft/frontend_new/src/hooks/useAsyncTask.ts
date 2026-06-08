'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AbortError } from '@/services/apiClient';

interface AsyncTaskState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

export function useAsyncTask<T>() {
  const [state, setState] = useState<AsyncTaskState<T>>({
    data: null,
    error: null,
    loading: false,
  });
  const controllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  const run = useCallback(
    async (task: (signal: AbortSignal) => Promise<T>) => {
      cancel();

      const controller = new AbortController();
      const runId = runIdRef.current + 1;
      runIdRef.current = runId;
      controllerRef.current = controller;

      setState((current) => ({
        ...current,
        error: null,
        loading: true,
      }));

      try {
        const data = await task(controller.signal);
        if (runIdRef.current === runId && !controller.signal.aborted) {
          setState({ data, error: null, loading: false });
        }
        return data;
      } catch (error) {
        if (error instanceof AbortError || controller.signal.aborted) {
          return null;
        }

        const normalized =
          error instanceof Error ? error : new Error('Unknown async task error');
        if (runIdRef.current === runId) {
          setState((current) => ({
            ...current,
            error: normalized,
            loading: false,
          }));
        }
        throw normalized;
      }
    },
    [cancel]
  );

  useEffect(() => cancel, [cancel]);

  const setData = useCallback((data: T | null) => {
    setState((current) => ({ ...current, data }));
  }, []);

  return useMemo(
    () => ({
      ...state,
      run,
      cancel,
      setData,
    }),
    [cancel, run, setData, state]
  );
}
