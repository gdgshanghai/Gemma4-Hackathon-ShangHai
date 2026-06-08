'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PixelButton, PixelCard } from '@/components/pixel';
import { DEMO_STEPS } from '@/utils/demoFlow';

interface DemoGuideBarProps {
  currentStep: number;
  nextStepTitle?: string;
  nextStepAction?: string | (() => void);
}

export default function DemoGuideBar({
  currentStep,
  nextStepTitle = '下一步',
  nextStepAction,
}: DemoGuideBarProps) {
  const router = useRouter();
  const [showAllSteps, setShowAllSteps] = useState(false);
  const currentStepData = DEMO_STEPS.find((step) => step.id === currentStep);
  const progress = (currentStep / DEMO_STEPS.length) * 100;

  useEffect(() => {
    if (typeof nextStepAction === 'string' && nextStepAction.startsWith('/')) {
      router.prefetch(nextStepAction);
    }
  }, [nextStepAction, router]);

  const handleNext = () => {
    if (!nextStepAction) return;

    if (typeof nextStepAction === 'function') {
      nextStepAction();
      return;
    }

    if (nextStepAction.startsWith('/')) {
      router.push(nextStepAction);
      return;
    }

    window.open(nextStepAction, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="mb-6">
      <PixelCard className="max-w-[1440px] overflow-hidden border-amber-600/70 bg-slate-950/90 p-4">
        <div className="mb-4 flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center border-2 border-amber-500 bg-amber-400 text-lg font-black text-slate-950 shadow-[inset_-3px_-3px_0_rgba(146,64,14,0.85)]">
              AI
            </span>
            <div>
              <h3 className="pixel-title text-xl text-amber-300">MVP 演示指引</h3>
              <p className="mt-1 text-sm text-slate-300">{currentStepData?.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="border-2 border-amber-500/70 bg-amber-500/10 px-4 py-2">
              <span className="text-lg font-bold text-amber-100">
                步骤 {currentStep} / {DEMO_STEPS.length}
              </span>
            </div>
            <button
              onClick={() => setShowAllSteps(!showAllSteps)}
              className="border-2 border-slate-600 bg-slate-900 px-3 py-1 text-sm text-slate-300 hover:border-amber-500 hover:text-amber-200"
            >
              {showAllSteps ? '收起' : '展开'}
            </button>
          </div>
        </div>

        <div className="mb-4">
          <div className="w-full border-2 border-slate-700 bg-slate-950 p-1">
            <div
              className="h-3 bg-gradient-to-r from-amber-500 via-yellow-300 to-emerald-400 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="mb-4 hidden md:block">
          <div className="flex gap-2 overflow-x-auto pb-2">
            {DEMO_STEPS.map((step) => {
              const isActive = step.id === currentStep;
              const isCompleted = step.id < currentStep;

              return (
                <div
                  key={step.id}
                  className={`min-w-[120px] shrink-0 border-2 p-3 transition-all duration-200 ${
                    isActive
                      ? 'border-amber-400 bg-amber-500/15 text-amber-100 shadow-[0_0_18px_rgba(245,158,11,0.25)]'
                      : isCompleted
                        ? 'border-emerald-500/70 bg-emerald-500/10 text-emerald-100'
                        : 'border-slate-700 bg-slate-900/70 text-slate-300'
                  }`}
                  title={step.fullLabel}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold">{isCompleted ? '✓' : step.id}</span>
                    <span className="whitespace-nowrap text-sm font-medium">{step.shortLabel}</span>
                  </div>
                  {isActive ? <div className="mt-1 truncate text-xs text-amber-200">{step.fullLabel}</div> : null}
                </div>
              );
            })}
          </div>
        </div>

        {showAllSteps ? (
          <div className="mb-4 border-2 border-slate-700 bg-slate-900/70 p-3 md:hidden">
            <h4 className="mb-2 font-bold text-slate-300">完整步骤</h4>
            <div className="space-y-2">
              {DEMO_STEPS.map((step) => {
                const isActive = step.id === currentStep;
                const isCompleted = step.id < currentStep;
                return (
                  <div
                    key={step.id}
                    className={`flex items-center gap-2 border-2 p-2 ${
                      isActive ? 'border-amber-400 bg-amber-500/15' : isCompleted ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700'
                    }`}
                  >
                    <span className="flex h-6 w-6 items-center justify-center border-2">{isCompleted ? '✓' : step.id}</span>
                    <span className="text-sm">{step.fullLabel}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        <div className="mb-4 flex items-center justify-between border-2 border-slate-700 bg-slate-900/70 p-3 md:hidden">
          <div>
            <div className="text-xs text-slate-400">步骤 {currentStep} / {DEMO_STEPS.length}</div>
            <div className="font-bold text-amber-300">{currentStepData?.fullLabel}</div>
          </div>
        </div>

        {nextStepAction ? (
          <div className="flex justify-center">
            <PixelButton variant="primary" onClick={handleNext} className="px-6 py-3 text-base">
              继续：{nextStepTitle}
            </PixelButton>
          </div>
        ) : null}
      </PixelCard>
    </div>
  );
}
