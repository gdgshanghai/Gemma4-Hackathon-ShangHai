'use client';

import React, { useState, useEffect } from 'react';
import { PixelCard } from '@/components/pixel';

export type LoadingVariant = 'card' | 'page' | 'inline';

interface LoadingStateProps {
  message?: string;
  /** 骨架屏变体（可选，默认使用 card 样式包裹） */
  variant?: LoadingVariant;
}

export default function LoadingState({
  message = '加载中...',
  variant,
}: LoadingStateProps) {
  // 终端风格加载点动画
  const [dots, setDots] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(d => (d + 1) % 4);
    }, 400);
    return () => clearInterval(interval);
  }, []);

  const terminalText = 'LOADING' + '.'.repeat(dots);

  // variant 为 inline 时直接渲染内联骨架
  if (variant === 'inline') {
    return (
      <div className="flex flex-col gap-2 w-full">
        <div className="flex items-center gap-2">
          <PixelSkeletonBlock className="w-8 h-8" />
          <PixelSkeletonBlock className="w-32 h-4" />
        </div>
        <p className="terminal-text text-xs font-bold tracking-wider">
          {terminalText}
        </p>
      </div>
    );
  }

  // variant 为 page 时渲染整页骨架
  if (variant === 'page') {
    return <PageSkeleton message={message} terminalText={terminalText} />;
  }

  // 默认 / card 模式
  return <CardSkeleton message={message} terminalText={terminalText} />;
}

// ========== 像素骨架块 ==========

function PixelSkeletonBlock({ className = '' }: { className?: string }) {
  return (
    <div
      className={`pixel-blink bg-slate-700 ${className}`}
      style={{
        boxShadow: 'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #334155',
      }}
    />
  );
}

// ========== Card 变体骨架屏 ==========

function CardSkeleton({
  message,
  terminalText,
}: {
  message: string;
  terminalText: string;
}) {
  return (
    <PixelCard className="p-8">
      <div className="flex flex-col items-center justify-center text-center">
        {/* 终端风格加载文字 */}
        <div className="mb-5 font-bold text-sm tracking-[4px] text-amber-400/80 font-mono">
          {terminalText}
        </div>

        {/* 骨架块卡片模拟 */}
        <div className="w-full max-w-xs space-y-4 mb-5">
          {/* 标题骨架 */}
          <PixelSkeletonBlock className="w-3/4 h-5 mx-auto" />

          {/* 内容行骨架 */}
          <div className="space-y-2.5">
            <PixelSkeletonBlock className="w-full h-3" />
            <PixelSkeletonBlock className="w-5/6 h-3" />
            <PixelSkeletonBlock className="w-2/3 h-3" />
          </div>

          {/* 进度条骨架 */}
          <div
            className="w-full h-5 bg-slate-900 border-2 border-slate-600"
            style={{
              boxShadow: 'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #334155',
            }}
          >
            <PixelSkeletonBlock className="w-1/2 h-full" />
          </div>
        </div>

        {/* 加载提示 */}
        <p className="text-slate-400 text-sm">{message}</p>
      </div>
    </PixelCard>
  );
}

// ========== Page 变体骨架屏 ==========

function PageSkeleton({
  message,
  terminalText,
}: {
  message: string;
  terminalText: string;
}) {
  return (
    <div className="w-full space-y-6 p-4">
      {/* 顶部导航栏骨架 */}
      <div className="flex items-center justify-between">
        <PixelSkeletonBlock className="w-40 h-7" />
        <div className="flex gap-3">
          <PixelSkeletonBlock className="w-16 h-7" />
          <PixelSkeletonBlock className="w-16 h-7" />
          <PixelSkeletonBlock className="w-16 h-7" />
        </div>
      </div>

      {/* 主卡片骨架 */}
      <PixelCard>
        <div className="space-y-5">
          {/* 标题行 */}
          <div className="flex items-center justify-between">
            <PixelSkeletonBlock className="w-48 h-6" />
            <PixelSkeletonBlock className="w-20 h-6" />
          </div>

          {/* 内容块 */}
          <div className="space-y-3">
            <PixelSkeletonBlock className="w-full h-4" />
            <PixelSkeletonBlock className="w-11/12 h-4" />
            <PixelSkeletonBlock className="w-3/4 h-4" />
            <PixelSkeletonBlock className="w-4/5 h-4" />
          </div>

          {/* 两个并排小块 */}
          <div className="flex gap-4">
            <div className="flex-1 space-y-2">
              <PixelSkeletonBlock className="w-full h-16" />
            </div>
            <div className="flex-1 space-y-2">
              <PixelSkeletonBlock className="w-full h-16" />
            </div>
          </div>

          {/* 底部按钮区 */}
          <div className="flex justify-end gap-3">
            <PixelSkeletonBlock className="w-20 h-8" />
            <PixelSkeletonBlock className="w-24 h-8" />
          </div>
        </div>
      </PixelCard>

      {/* 次级卡片骨架 */}
      <PixelCard>
        <div className="space-y-4">
          <PixelSkeletonBlock className="w-36 h-6" />
          <div className="space-y-2">
            {[0, 1, 2].map(i => (
              <div key={i} className="flex items-center gap-3">
                <PixelSkeletonBlock className="w-8 h-8 flex-shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <PixelSkeletonBlock className="w-2/3 h-3.5" />
                  <PixelSkeletonBlock className="w-full h-2.5" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </PixelCard>

      {/* 加载状态栏 */}
      <div className="flex items-center justify-center gap-2 text-xs terminal-text font-bold tracking-wider">
        <span>{terminalText}</span>
        <span className="text-slate-400 font-normal tracking-normal">
          {message}
        </span>
      </div>
    </div>
  );
}