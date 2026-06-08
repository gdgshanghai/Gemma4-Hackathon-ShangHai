'use client';

import React from 'react';
import { PixelButton, PixelCard } from '@/components/pixel';

interface AppErrorBoundaryProps {
  children: React.ReactNode;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

export default class AppErrorBoundary extends React.Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[CareerCraft] UI boundary caught an error:', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen crt-screen bg-slate-950 p-6 text-slate-100">
        <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
          <PixelCard className="w-full border-red-700 bg-red-950/20 p-8">
            <div className="space-y-5 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center border-4 border-red-500 bg-red-900/40 text-3xl font-bold text-red-200">
                !
              </div>
              <div>
                <h1 className="pixel-title text-xl text-red-300">
                  SYSTEM ERROR
                </h1>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                  CareerCraft hit a client-side rendering issue. Your local
                  progress is preserved; reload to return to the last stable
                  checkpoint.
                </p>
              </div>
              <pre className="max-h-40 overflow-auto border-2 border-slate-700 bg-slate-950 p-3 text-left text-xs text-red-200">
                {this.state.error.message}
              </pre>
              <PixelButton onClick={() => window.location.reload()}>
                RELOAD
              </PixelButton>
            </div>
          </PixelCard>
        </div>
      </div>
    );
  }
}
