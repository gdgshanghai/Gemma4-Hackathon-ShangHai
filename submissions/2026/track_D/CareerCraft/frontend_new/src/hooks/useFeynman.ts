'use client';

import { useCallback } from 'react';
import { feedbackService } from '@/services/feedbackService';
import { useAsyncTask } from './useAsyncTask';

export function useFeynman() {
  const task = useAsyncTask<{ status: string; feedback: string }>();
  const { cancel, data, error, loading, run } = task;

  const submitAnswer = useCallback(
    async (missionId: string, answer: string) => {
      return run((signal) => feedbackService.submitFeynmanAnswer(missionId, answer, signal));
    },
    [run]
  );

  return {
    result: data,
    loading,
    error,
    submitAnswer,
    cancel,
  };
}
