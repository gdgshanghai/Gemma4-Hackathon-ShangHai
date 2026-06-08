'use client';

import React from 'react';
import { PixelBadge, PixelButton, PixelTextarea } from '@/components/pixel';

interface FeynmanAnswerBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export default function FeynmanAnswerBox({
  value,
  onChange,
  onSubmit,
  disabled = false,
}: FeynmanAnswerBoxProps) {
  const charCount = value.length;
  const minCharCount = 30;
  const meetsRequirement = charCount >= minCharCount;
  const progressPercent = Math.min((charCount / minCharCount) * 100, 100);

  return (
    <section className="border-4 border-slate-700 bg-slate-950/82 p-5 backdrop-blur-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="font-bold text-amber-300">你的解释</h3>
        <PixelBadge variant={meetsRequirement ? 'success' : 'warning'}>
          {charCount} / {minCharCount} 字
        </PixelBadge>
      </div>

      <PixelTextarea
        value={value}
        onChange={onChange}
        placeholder="像给同学讲题一样解释：这个概念是什么，为什么有用，在当前任务里怎么用。"
        rows={7}
        disabled={disabled}
      />

      <div className="mt-3 h-3 border-2 border-slate-700 bg-slate-900">
        <div
          className={`h-full transition-all ${meetsRequirement ? 'bg-emerald-500' : 'bg-amber-500'}`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {!meetsRequirement ? (
        <p className="mt-2 text-xs text-slate-500">
          还需要 {minCharCount - charCount} 个字。可以补一个生活类比或任务中的例子。
        </p>
      ) : null}

      <PixelButton onClick={onSubmit} disabled={!meetsRequirement || disabled} fullWidth className="mt-4">
        {disabled ? '提交中...' : '提交解释'}
      </PixelButton>
    </section>
  );
}
