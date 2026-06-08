import React, { useEffect, useState } from 'react';
import { PixelBadge, PixelCard } from '@/components/pixel';

interface SubmissionRecord {
  missionId: string;
  submittedAt: string;
  reportLength: number;
  qualityScore: number;
  status: 'submitted';
}

interface SubmissionHistoryPanelProps {
  missionId: string;
}

export default function SubmissionHistoryPanel({ missionId }: SubmissionHistoryPanelProps) {
  const storageKey = `careercraft-submission-history-${missionId}`;
  const [history, setHistory] = useState<SubmissionRecord[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    setHistory(saved ? JSON.parse(saved) : []);
  }, [storageKey]);

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleString('zh-CN', {
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

  return (
    <PixelCard title="提交记录">
      {history.length === 0 ? (
        <p className="py-5 text-center text-sm text-slate-500">还没有正式提交记录。</p>
      ) : (
        <div className="space-y-3">
          {history.slice(0, 3).map((record, index) => (
            <div key={`${record.submittedAt}-${index}`} className="border-2 border-slate-700 bg-slate-900/70 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="mb-2 text-xs text-slate-400">{formatDate(record.submittedAt)}</p>
                  <PixelBadge variant="success">已提交</PixelBadge>
                </div>
                <div className="text-right text-sm">
                  <p className="font-bold text-amber-300">{record.qualityScore} / 5</p>
                  <p className="text-xs text-slate-500">自检项</p>
                </div>
              </div>
              <p className="mt-3 text-xs text-slate-400">报告长度：{record.reportLength} 字</p>
            </div>
          ))}
        </div>
      )}
    </PixelCard>
  );
}
