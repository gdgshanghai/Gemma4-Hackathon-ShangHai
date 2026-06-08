'use client';

import React from 'react';

interface DemoHighlightProps {
  children: React.ReactNode;
  targetStep: number;
  currentStep: number;
  label?: string;
  className?: string;
}

export default function DemoHighlight({
  children,
  targetStep,
  currentStep,
  label = '当前演示操作区',
  className = '',
}: DemoHighlightProps) {
  const isActive = targetStep === currentStep;
  
  if (!isActive) {
    return <>{children}</>;
  }
  
  return (
    <div className={`relative ${className}`}>
      <div className="absolute -top-2 -right-2 z-10">
        <div className="border-2 border-amber-400 bg-slate-950 px-3 py-1 text-xs font-bold text-amber-200 shadow-[0_0_18px_rgba(245,158,11,0.28)]">
          MVP / {label}
        </div>
      </div>
      <div className="relative border-4 border-amber-500 shadow-[0_0_28px_rgba(245,158,11,0.28)]">
        {children}
      </div>
    </div>
  );
}
