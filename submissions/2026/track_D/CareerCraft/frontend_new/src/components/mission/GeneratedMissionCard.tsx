import React from 'react';
import { PixelBadge, PixelButton, PixelCard } from '@/components/pixel';

export interface GeneratedMission {
  id: string;
  title: string;
  aiLead: string;
  businessBackground: string;
  objectives: string[];
  deliverables: string[];
  reviewCriteria: string[];
  recommendedSkills: string[];
  recommendedResources: string[];
  estimatedTime: string;
  rewardXP: number;
  difficulty: string;
  type: string;
  mockDataUrl?: string;
}

interface GeneratedMissionCardProps {
  mission: GeneratedMission;
  source?: 'api' | 'fallback';
  onAccept: () => void;
  onRegenerate: () => void;
  onClose: () => void;
}

const DIFFICULTY_TEXT: Record<string, { badge: 'fun' | 'honor' | 'warning'; text: string }> = {
  easy: { badge: 'fun', text: '入门' },
  medium: { badge: 'honor', text: '进阶' },
  hard: { badge: 'warning', text: '挑战' },
};

const TYPE_TEXT: Record<string, { badge: 'neutral' | 'honor' | 'warning' | 'fun'; text: string }> = {
  ticket: { badge: 'neutral', text: '企业工单' },
  project: { badge: 'honor', text: '项目委托' },
  interview: { badge: 'warning', text: '面试实战' },
  feynman: { badge: 'fun', text: '费曼讲解型' },
};

export default function GeneratedMissionCard({ mission, source, onAccept, onRegenerate, onClose }: GeneratedMissionCardProps) {
  const difficultyConfig = DIFFICULTY_TEXT[mission.difficulty] || DIFFICULTY_TEXT.easy;
  const typeConfig = TYPE_TEXT[mission.type] || TYPE_TEXT.ticket;

  return (
    <div className="space-y-4">
      <PixelCard title={mission.title}>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <PixelBadge variant={difficultyConfig.badge}>{difficultyConfig.text}</PixelBadge>
            <PixelBadge variant={typeConfig.badge}>{typeConfig.text}</PixelBadge>
            <PixelBadge variant="honor">+{mission.rewardXP} XP</PixelBadge>
            <PixelBadge variant="neutral">{mission.estimatedTime}</PixelBadge>
            {source ? (
              <PixelBadge variant={source === 'api' ? 'success' : 'warning'}>
                {source === 'api' ? 'API' : 'Fallback'}
              </PixelBadge>
            ) : null}
          </div>
          <div className="border-2 border-slate-700 bg-slate-950 p-3">
            <div className="mb-1 text-sm font-bold text-amber-300">{mission.aiLead}</div>
            <p className="leading-7 text-slate-300">{mission.businessBackground}</p>
          </div>
          {mission.mockDataUrl ? (
            <PixelButton
              variant="secondary"
              onClick={() => window.open(mission.mockDataUrl, '_blank', 'noopener,noreferrer')}
            >
              下载任务数据集
            </PixelButton>
          ) : null}
        </div>
      </PixelCard>

      <MissionList title="任务目标" items={mission.objectives} marker="OBJ" />
      <MissionList title="交付物" items={mission.deliverables} marker="OUT" />
      <MissionList title="评审标准" items={mission.reviewCriteria} marker="QA" />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <PixelCard title="推荐技能">
          <div className="flex flex-wrap gap-2">
            {mission.recommendedSkills.map((skill, idx) => (
                  <PixelBadge key={`skill-${idx}`} variant="fun">
                {skill}
              </PixelBadge>
            ))}
          </div>
        </PixelCard>

        <PixelCard title="推荐资源">
          <ul className="space-y-2">
            {mission.recommendedResources.map((resource, idx) => (
                  <li key={`resource-${idx}`} className="flex items-start gap-2 text-sm leading-6 text-slate-300">
                <span className="font-mono text-amber-400">›</span>
                <span>{resource}</span>
              </li>
            ))}
          </ul>
        </PixelCard>
      </div>

      <div className="flex flex-wrap justify-end gap-3">
        <PixelButton variant="secondary" onClick={onClose}>
          关闭
        </PixelButton>
        <PixelButton variant="secondary" onClick={onRegenerate}>
          重新生成
        </PixelButton>
        <PixelButton onClick={onAccept}>接受这个任务</PixelButton>
      </div>
    </div>
  );
}

function MissionList({ title, items, marker }: { title: string; items: string[]; marker: string }) {
  return (
    <PixelCard title={title}>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={`${marker}-${index}`} className="flex items-start gap-3 text-sm leading-6 text-slate-300">
            <span className="font-mono font-bold text-amber-400">{marker}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </PixelCard>
  );
}
