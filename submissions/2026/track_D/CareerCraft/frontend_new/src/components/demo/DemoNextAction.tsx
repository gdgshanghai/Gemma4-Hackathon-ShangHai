'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { PixelButton, PixelCard } from '@/components/pixel';

interface DemoNextActionProps {
  step: number;
  title: string;
  description: string;
  buttonText: string;
  buttonAction: string;
  highlightElement?: string;
}

export default function DemoNextAction({
  step,
  title,
  description,
  buttonText,
  buttonAction,
  highlightElement,
}: DemoNextActionProps) {
  const router = useRouter();

  useEffect(() => {
    if (buttonAction.startsWith('/')) {
      router.prefetch(buttonAction);
    }
  }, [buttonAction, router]);

  const handleClick = () => {
    if (buttonAction.startsWith('/')) {
      router.push(buttonAction);
      return;
    }
    window.open(buttonAction, '_blank', 'noopener,noreferrer');
  };

  return (
    <PixelCard className="mb-6 border-amber-500 bg-amber-950/30 p-5 shadow-lg shadow-amber-500/20">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center border-2 border-amber-500 bg-slate-950 font-mono text-sm font-bold text-amber-300">
          {String(step).padStart(2, '0')}
        </div>
        <div className="flex-1">
          <h4 className="mb-2 text-lg font-bold text-amber-300">下一步：{title}</h4>
          <p className="mb-4 text-sm leading-6 text-slate-300">{description}</p>

          {highlightElement ? (
            <div className="mb-3 border border-amber-600/50 bg-amber-900/30 p-2">
              <p className="text-xs text-amber-300">提示：从页面里高亮标识的模块继续操作。</p>
            </div>
          ) : null}

          <PixelButton variant="primary" onClick={handleClick} className="px-6 py-3 text-lg">
            {buttonText}
          </PixelButton>
        </div>
      </div>
    </PixelCard>
  );
}
