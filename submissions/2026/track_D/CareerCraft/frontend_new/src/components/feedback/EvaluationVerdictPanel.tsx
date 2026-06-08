import React from 'react';
import Image from 'next/image';
import { PixelBadge, PixelCard, PixelProgress } from '@/components/pixel';
import { getMentorImage } from '@/constants/images';

interface EvaluationVerdictProps {
  isSoftwareEngineer: boolean;
  isPassed: boolean;
  grade: string;
  totalScore: number;
  maxScore: number;
  summary: string;
}

export default function EvaluationVerdictPanel({
  isSoftwareEngineer,
  isPassed,
  grade,
  totalScore,
  maxScore,
  summary,
}: EvaluationVerdictProps) {
  const careerId = isSoftwareEngineer ? 'software-engineer' : 'data-analyst';
  const mentorName = isSoftwareEngineer ? '工程导师' : '数据导师';
  const focus = isSoftwareEngineer
    ? ['复现路径', '代码正确性', '测试覆盖']
    : ['指标口径', '分析链路', '业务建议'];
  const scorePercent = (totalScore / maxScore) * 100;

  return (
    <PixelCard title="评审结论">
      <div className="space-y-4">
        <div className="flex items-center gap-4 border-2 border-slate-700 bg-slate-950/50 p-3">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden border-2 border-amber-500 bg-slate-900">
            <Image src={getMentorImage(careerId)} alt={mentorName} fill className="object-cover" sizes="64px" />
          </div>
          <div>
            <h4 className="font-bold text-amber-300">{mentorName}</h4>
            <p className="mt-1 text-xs text-slate-400">关注：{focus.join(' / ')}</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="border-2 border-slate-700 bg-slate-900/70 p-3 text-center">
            <p className="mb-2 text-xs text-slate-400">结论</p>
            <PixelBadge variant={isPassed ? 'success' : 'warning'}>
              {isPassed ? '通过' : '建议重试'}
            </PixelBadge>
          </div>
          <div className="border-2 border-slate-700 bg-slate-900/70 p-3 text-center">
            <p className="mb-1 text-xs text-slate-400">等级</p>
            <p className="pixel-title text-3xl text-amber-300">{grade}</p>
          </div>
          <div className="border-2 border-slate-700 bg-slate-900/70 p-3 text-center">
            <p className="mb-1 text-xs text-slate-400">总分</p>
            <p className="text-xl font-bold text-emerald-300">
              {totalScore}/{maxScore}
            </p>
          </div>
        </div>

        <PixelProgress value={scorePercent} color={scorePercent >= 80 ? '#10b981' : '#f59e0b'} />

        <div className="border-2 border-amber-700 bg-amber-950/30 p-4">
          <p className="mb-2 text-sm font-bold text-amber-300">导师总结</p>
          <p className="text-sm leading-6 text-slate-200">{summary}</p>
        </div>
      </div>
    </PixelCard>
  );
}
