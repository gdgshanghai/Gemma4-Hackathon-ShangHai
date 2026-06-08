import React, { useMemo, useState } from 'react';
import { PixelButton, PixelCard, PixelBadge } from '@/components/pixel';

interface SubmissionQualityPanelProps {
  report: string;
}

export default function SubmissionQualityPanel({ report }: SubmissionQualityPanelProps) {
  const [showPreview, setShowPreview] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);

  const preview = useMemo(() => {
    const length = report.trim().length;
    if (length >= 260) {
      return {
        label: '接近可提交',
        variant: 'success' as const,
        score: '82 - 90',
        tips: ['内容较完整，可以再补一句结论的优先级。', '如果有数据口径或测试方式，建议放进附加材料。'],
      };
    }
    if (length >= 120) {
      return {
        label: '需要补强',
        variant: 'warning' as const,
        score: '70 - 82',
        tips: ['报告已有主干，建议补充任务背景和关键证据。', '把建议写成可以执行的 1-2 个动作。'],
      };
    }
    return {
      label: '草稿阶段',
      variant: 'danger' as const,
      score: '待完善',
      tips: ['先写清楚你解决了什么问题。', '至少补齐背景、过程、结论三个部分。'],
    };
  }, [report]);

  const handlePreview = () => {
    setIsPreviewing(true);
    setTimeout(() => {
      setShowPreview(true);
      setIsPreviewing(false);
    }, 700);
  };

  return (
    <PixelCard title="导师预审">
      <div className="space-y-4">
        <p className="text-sm leading-6 text-slate-300">
          先做一次轻量预审，帮助你在正式提交前发现结构问题。
        </p>
        <PixelButton
          variant="secondary"
          onClick={handlePreview}
          disabled={isPreviewing || !report.trim()}
          fullWidth
        >
          {isPreviewing ? '预审中...' : '运行预审'}
        </PixelButton>

        {showPreview && (
          <div className="space-y-3 border-2 border-amber-700 bg-slate-950/70 p-4">
            <div className="flex items-center justify-between gap-3">
              <PixelBadge variant={preview.variant}>{preview.label}</PixelBadge>
              <span className="text-sm font-bold text-amber-300">{preview.score}</span>
            </div>
            <ul className="space-y-2 text-sm text-slate-300">
              {preview.tips.map((tip) => (
                <li key={tip} className="border-l-2 border-amber-500 pl-3">
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </PixelCard>
  );
}
