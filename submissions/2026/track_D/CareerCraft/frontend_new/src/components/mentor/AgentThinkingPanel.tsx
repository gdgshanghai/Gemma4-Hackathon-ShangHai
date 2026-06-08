import React from 'react';
import { PixelCard } from '@/components/pixel';

interface AgentThinkingPanelProps {
  careerId: string;
}

const careerThinkingContent = {
  'software-engineer': {
    header: '我对这个任务的理解是：',
    points: [
      '这是一个典型的调试问题',
      '关键在于找出问题复现的最小条件',
      '建议先写单元测试复现，再修复',
      '注意边界情况的处理'
    ]
  },
  'data-analyst': {
    header: '我对这个任务的理解是：',
    points: [
      '这是一个用户行为分析问题',
      '关键在于拆解活跃度下降的维度',
      '建议从时间、用户分层、功能使用入手',
      '注意数据质量和异常值检测'
    ]
  }
};

export default function AgentThinkingPanel({ careerId }: AgentThinkingPanelProps) {
  const content = careerThinkingContent[careerId as keyof typeof careerThinkingContent] 
    || careerThinkingContent['software-engineer'];

  return (
    <PixelCard title="🧠 AI 分析中...">
      <div className="space-y-4">
        <p className="text-amber-400 font-medium">{content.header}</p>
        <div className="space-y-2">
          {content.points.map((point, index) => (
            <div
              key={index}
              className="flex items-start gap-2 p-2 bg-slate-800/50 border-l-3 border-amber-500"
            >
              <span className="text-amber-500 mt-1">●</span>
              <p className="text-slate-300 text-sm">{point}</p>
            </div>
          ))}
        </div>
        <div className="text-xs text-slate-500 italic flex items-center gap-1">
          <span>思考深度：</span>
          <span className="text-green-400">高</span>
        </div>
      </div>
    </PixelCard>
  );
}
