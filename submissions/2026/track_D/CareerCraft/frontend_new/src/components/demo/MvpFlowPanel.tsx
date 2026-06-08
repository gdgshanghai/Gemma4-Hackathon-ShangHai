'use client';

import React from 'react';
import { PixelBadge, PixelCard } from '@/components/pixel';
import { DEMO_STEPS } from '@/utils/demoFlow';

const apiCoverage = [
  { label: '职业列表', endpoint: '/api/v1/careers', mode: '真实优先' },
  { label: '任务生成', endpoint: '/api/v1/missions/generate', mode: '真实优先' },
  { label: 'RAG 资源', endpoint: '/api/v1/careers/resources', mode: '真实优先' },
  { label: '费曼挑战', endpoint: '/api/v1/user/feynman/submit', mode: '真实优先' },
  { label: 'AI 评审', endpoint: '/api/v1/missions/evaluate', mode: '真实优先' },
  { label: '作品集', endpoint: 'localStorage + Mock 档案', mode: '演示兜底' },
];

export default function MvpFlowPanel() {
  return (
    <PixelCard className="bg-slate-950/86 border-slate-700 p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <PixelBadge variant="warning">MVP 主线闭环</PixelBadge>
          <h2 className="pixel-title mt-3 text-2xl text-amber-300">从职业草图到成长档案</h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
            演示路径围绕计算机系大学生的第一次职业模拟展开：选择数据山脉，
            接受真实业务任务，检索学习资源，完成费曼解释，提交分析报告，再由 AI 导师给出评审并沉淀作品集。
          </p>
        </div>
        <div className="border-2 border-amber-500/60 bg-amber-500/10 px-4 py-3 text-sm text-amber-100 italic">
          「每一次代码运行，都是向梦想迈进的一步」
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-2 md:grid-cols-4">
        {DEMO_STEPS.map((step) => (
          <div
            key={step.id}
            className="border-2 border-slate-700 bg-slate-900/80 p-3 shadow-[inset_-3px_-3px_0_rgba(15,23,42,0.9),inset_3px_3px_0_rgba(71,85,105,0.55)]"
          >
            <div className="text-xs font-bold text-amber-300">#{String(step.id).padStart(2, '0')}</div>
            <div className="mt-1 text-sm font-bold text-slate-100">{step.fullLabel}</div>
            <div className="mt-1 text-xs leading-5 text-slate-400">{step.description}</div>
          </div>
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-2 md:grid-cols-3">
        {apiCoverage.map((item) => (
          <div key={item.endpoint} className="border-2 border-slate-700 bg-slate-900/70 p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-bold text-slate-100">{item.label}</span>
              <span className="text-xs text-emerald-300">{item.mode}</span>
            </div>
            <div className="mt-2 break-all font-mono text-[11px] text-slate-400">{item.endpoint}</div>
          </div>
        ))}
      </div>
    </PixelCard>
  );
}
