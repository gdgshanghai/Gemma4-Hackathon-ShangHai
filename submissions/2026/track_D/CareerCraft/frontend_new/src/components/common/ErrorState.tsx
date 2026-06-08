'use client';

import React from 'react';
import { PixelCard, PixelButton } from '@/components/pixel';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({ 
  title = '出错了',
  message = '加载数据时出现问题，请重试',
  onRetry
}: ErrorStateProps) {
  return (
    <PixelCard className="p-8">
      <div className="flex flex-col items-center justify-center text-center">
        <div className="text-5xl mb-4 text-red-400">⚠️</div>
        <h3 className="text-xl font-bold text-red-400 mb-2">{title}</h3>
        <p className="text-slate-400 mb-6">{message}</p>
        {onRetry && (
          <PixelButton onClick={onRetry}>
            🔄 重试
          </PixelButton>
        )}
      </div>
    </PixelCard>
  );
}
