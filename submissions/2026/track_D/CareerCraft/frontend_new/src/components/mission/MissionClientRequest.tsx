import React from 'react';
import { PixelBadge } from '@/components/pixel';
import { Mission } from '@/types';

interface MissionClientRequestProps {
  mission: Mission;
}

const CAREER_CLIENT_CONFIG = {
  'software-engineer': {
    client: '后端服务团队',
    riskText: '不要直接改代码，先确认复现路径和问题边界。',
  },
  'data-analyst': {
    client: '增长运营团队',
    riskText: '不要只看表面趋势，要检查异常值、口径和用户分层。',
  },
};

export default function MissionClientRequest({ mission }: MissionClientRequestProps) {
  const config = CAREER_CLIENT_CONFIG[mission.careerId as keyof typeof CAREER_CLIENT_CONFIG] ??
    CAREER_CLIENT_CONFIG['software-engineer'];

  return (
    <section className="border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-300">Client Request</div>
          <h2 className="mt-2 text-xl font-bold text-amber-300">委托方需求</h2>
        </div>
        <PixelBadge variant="neutral">{config.client}</PixelBadge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="border border-slate-700 bg-slate-900/56 p-4">
          <h3 className="mb-2 font-bold text-slate-100">需求描述</h3>
          <p className="text-sm leading-6 text-slate-300">{mission.description}</p>
        </div>

        <div className="border border-amber-700/70 bg-amber-950/18 p-4">
          <h3 className="mb-2 font-bold text-amber-300">风险提醒</h3>
          <p className="text-sm leading-6 text-amber-100/80">{config.riskText}</p>
        </div>
      </div>

      <div className="mt-4 border border-slate-700 bg-slate-900/56 p-4">
        <h3 className="mb-2 font-bold text-slate-100">验收标准</h3>
        <ul className="space-y-2">
          {mission.criteria.map((criterion, index) => (
            <li key={index} className="flex gap-2 text-sm leading-6 text-slate-300">
              <span className="mt-2 h-2 w-2 shrink-0 bg-emerald-400" />
              <span>{criterion}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
