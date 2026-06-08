'use client';

import React from 'react';
import { PixelCard } from '@/components/pixel';

interface WorldMapLegendProps {
  className?: string;
}

export default function WorldMapLegend({ className = '' }: WorldMapLegendProps) {
  const legendItems = [
    { status: 'available', label: '可进入', color: 'text-emerald-300', bg: 'bg-emerald-950/60', border: 'border-emerald-500' },
    { status: 'in-progress', label: '训练中', color: 'text-amber-300', bg: 'bg-amber-950/60', border: 'border-amber-500' },
    { status: 'completed', label: '已完成', color: 'text-sky-300', bg: 'bg-sky-950/60', border: 'border-sky-500' },
    { status: 'locked', label: '即将开放', color: 'text-slate-400', bg: 'bg-slate-900/70', border: 'border-slate-600' },
  ];

  return (
    <PixelCard title="地图图例" className={className}>
      <div className="grid grid-cols-2 gap-3">
        {legendItems.map((item) => (
          <div key={item.status} className="flex items-center gap-2">
            <div className={`h-4 w-4 border-2 ${item.bg} ${item.border}`} />
            <span className={`text-sm ${item.color}`}>{item.label}</span>
          </div>
        ))}
      </div>
    </PixelCard>
  );
}
