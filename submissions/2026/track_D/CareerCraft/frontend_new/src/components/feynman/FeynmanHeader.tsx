'use client';

import React from 'react';
import { PixelBadge } from '@/components/pixel';

interface FeynmanHeaderProps {
  missionId: string;
}

export default function FeynmanHeader({ missionId }: FeynmanHeaderProps) {
  return (
    <section className="border-4 border-slate-700 bg-slate-950/80 p-6 text-center backdrop-blur-sm">
      <PixelBadge variant="warning">理解挑战</PixelBadge>
      <h1 className="pixel-title mt-4 text-3xl font-bold text-amber-300">费曼挑战室</h1>
      <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-300">
        用最简单的话解释任务里的核心概念。能讲给同学听懂，才说明你真的把职业技能吃透了。
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <PixelBadge variant="success">理解检测</PixelBadge>
        <PixelBadge variant="neutral">任务 #{missionId}</PixelBadge>
      </div>
    </section>
  );
}
