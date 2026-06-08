import React from 'react';
import { PROGRESS_COLORS } from '@/constants/designSystem';

type ProgressColor = keyof typeof PROGRESS_COLORS;

interface PixelProgressProps {
  value: number;
  label?: string;
  color?: ProgressColor | string;
  height?: string;
}

export default function PixelProgress({
  value,
  label,
  color = 'primary',
  height = 'h-6',
}: PixelProgressProps) {
  const safeValue = Math.max(0, Math.min(100, value));
  const barColor = (Object.values(PROGRESS_COLORS) as string[]).includes(color as string)
    ? color
    : PROGRESS_COLORS[color as ProgressColor] || PROGRESS_COLORS.primary;

  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between items-center mb-2">
          <span className="text-slate-300 font-medium">{label}</span>
          <span className="text-amber-400 font-bold">{safeValue}%</span>
        </div>
      )}
      <div
        className={`w-full ${height} bg-slate-900 border-4 border-slate-600`}
        style={{
          boxShadow:
            'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #334155',
        }}
      >
        <div
          className="h-full transition-all duration-300"
          style={{
            width: `${safeValue}%`,
            backgroundColor: barColor,
            boxShadow:
              `inset -2px -2px 0px 0px rgba(0,0,0,0.3), inset 2px 2px 0px 0px rgba(255,255,255,0.3)`,
          }}
        />
      </div>
    </div>
  );
}
