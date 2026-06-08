import React from 'react';
import { PixelBadge } from '@/components/pixel';

export default function LobbyFooter() {
  return (
    <footer className="mt-8 border-t-4 border-slate-700 py-6">
      <div className="mx-auto max-w-4xl px-4">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center border-2 border-amber-600 bg-slate-950 font-mono text-xs font-bold text-amber-300">
              CC
            </div>
            <div>
              <p className="text-lg font-bold text-amber-400">Lv.1 职业冒险者</p>
              <p className="text-sm text-slate-400">欢迎来到 CareerCraft 职业大陆</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Stat label="金币" value="0" />
            <Stat label="徽章" value="0" />
            <Stat label="任务" value="0" />
          </div>

          <div className="flex gap-2">
            <PixelBadge variant="neutral">新手</PixelBadge>
            <PixelBadge variant="fun">探索者</PixelBadge>
          </div>
        </div>
      </div>
    </footer>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs text-amber-300">{label}</span>
      <span className="font-bold text-slate-300">{value}</span>
    </div>
  );
}
