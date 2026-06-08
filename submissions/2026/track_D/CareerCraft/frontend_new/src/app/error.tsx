'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/common';

export default function AppRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[CareerCraft] route error:', error);
  }, [error]);

  return (
    <main className="min-h-screen crt-screen bg-slate-950 p-6 text-slate-100">
      <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
        <ErrorState
          title="SYSTEM CHECK FAILED"
          message="The current scene failed to load. Retry will restart this view without clearing saved progress."
          onRetry={reset}
        />
      </div>
    </main>
  );
}
