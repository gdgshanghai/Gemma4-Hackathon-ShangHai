import React from 'react';
import { PixelCard } from '@/components/pixel';

interface SubmissionEditorProps {
  report: string;
  code: string;
  onReportChange: (value: string) => void;
  onCodeChange: (value: string) => void;
  hasUnsavedChanges: boolean;
}

export default function SubmissionEditor({
  report,
  code,
  onReportChange,
  onCodeChange,
  hasUnsavedChanges,
}: SubmissionEditorProps) {
  const reportLength = report.trim().length;
  const meetsLengthRequirement = reportLength >= 30;

  return (
    <PixelCard className="overflow-hidden p-0">
      <div className="border-b-4 border-slate-700 bg-slate-950/80 px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="pixel-title text-lg text-amber-400">实训交付台</p>
            <p className="mt-2 text-sm text-slate-300">
              像给项目导师提交一次真实工作汇报：说明背景、分析过程、结论和下一步建议。
            </p>
          </div>
          <span
            className={`border-2 px-3 py-1 text-xs font-bold ${
              hasUnsavedChanges
                ? 'border-amber-500 bg-amber-950/50 text-amber-200'
                : 'border-emerald-500 bg-emerald-950/50 text-emerald-200'
            }`}
          >
            {hasUnsavedChanges ? '草稿未保存' : '草稿已同步'}
          </span>
        </div>
      </div>

      <div className="space-y-5 bg-slate-900/70 p-5">
        <label className="block">
          <span className="mb-2 block text-sm font-bold text-amber-300">任务报告</span>
          <textarea
            value={report}
            onChange={(event) => onReportChange(event.target.value)}
            placeholder={[
              '建议结构：',
              '1. 我理解的任务背景',
              '2. 我发现的关键问题',
              '3. 我的分析或实现过程',
              '4. 最终结论与可执行建议',
            ].join('\n')}
            rows={15}
            className="w-full resize-y border-4 border-slate-700 bg-slate-950/90 p-4 font-mono text-sm leading-6 text-slate-100 outline-none transition focus:border-amber-500"
            style={{
              boxShadow: 'inset -3px -3px 0 #020617, inset 3px 3px 0 #334155',
            }}
          />
        </label>

        <div className="flex flex-wrap items-center justify-between gap-3 border-y-2 border-slate-700/70 py-3 text-xs">
          <span className={meetsLengthRequirement ? 'text-emerald-300' : 'text-amber-300'}>
            报告字数：{reportLength} / 30+
          </span>
          <span className="text-slate-400">
            支持 Markdown。建议写得像作品集条目，而不是一句话答案。
          </span>
        </div>

        <label className="block">
          <span className="mb-2 block text-sm font-bold text-amber-300">
            附加材料或代码片段
          </span>
          <textarea
            value={code}
            onChange={(event) => onCodeChange(event.target.value)}
            placeholder="可粘贴 SQL、Python、链接、截图说明、实验记录等。没有代码也可以填写补充说明。"
            rows={8}
            className="w-full resize-y border-4 border-slate-700 bg-slate-950/90 p-4 font-mono text-sm leading-6 text-cyan-100 outline-none transition focus:border-cyan-500"
            style={{
              boxShadow: 'inset -3px -3px 0 #020617, inset 3px 3px 0 #334155',
            }}
          />
        </label>
      </div>
    </PixelCard>
  );
}
