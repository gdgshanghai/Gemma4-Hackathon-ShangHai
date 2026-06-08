import React from 'react';
import Image from 'next/image';
import { PixelBadge, PixelButton, PixelCard } from '@/components/pixel';
import AgentThinkingPanel from './AgentThinkingPanel';
import AgentMissionFeed from './AgentMissionFeed';
import FeynmanChallengeCard from './FeynmanChallengeCard';
import { Resource } from '@/types';
import { IMAGES } from '@/constants/images';

interface AIAgentPanelProps {
  careerId: string;
  resources: Resource[];
  missionId?: string;
  isDemoMode?: boolean;
  onOpenResourceDialog?: () => void;
  onOpenRAGDrawer?: () => void;
  onScrollToTasks?: () => void;
}

const mentorConfig = {
  'software-engineer': {
    name: 'AI 技术导师',
    title: '硅屿工程导航员',
    status: '在线',
    mode: '任务分析中',
    prompt: '先复现，再定位，最后用测试把结论固定下来。',
    image: IMAGES.SILICON_ISLE,
  },
  'data-analyst': {
    name: '增长数据 Lead',
    title: '数据山脉导师',
    status: '在线',
    mode: '任务准备中',
    prompt: '把业务问题拆成指标、分层和趋势，结论才会站得住。',
    image: IMAGES.MENTOR_DATA_GUIDE,
  },
  'product-designer': {
    name: '产品设计导师',
    title: '设计港引航员',
    status: '在线',
    mode: '需求梳理中',
    prompt: '先找到真实用户场景，再决定界面和功能怎么表达。',
    image: IMAGES.PRODUCT_DESIGN_HARBOR,
  },
  'ai-researcher': {
    name: 'AI 研究导师',
    title: '研究塔导师',
    status: '在线',
    mode: '实验规划中',
    prompt: '把假设写清楚，再用实验和评测去验证。',
    image: IMAGES.AI_RESEARCH_TOWER,
  },
};

export default function AIAgentPanel({
  careerId,
  resources,
  missionId,
  isDemoMode,
  onOpenResourceDialog,
  onOpenRAGDrawer,
  onScrollToTasks,
}: AIAgentPanelProps) {
  const config = mentorConfig[careerId as keyof typeof mentorConfig] || mentorConfig['software-engineer'];
  const isDataAnalyst = careerId === 'data-analyst';

  return (
    <div className="space-y-4">
      {isDemoMode && isDataAnalyst ? (
        <PixelCard className="border-amber-600 bg-amber-950/20">
          <div className="space-y-3">
            <div>
              <div className="mb-1 font-mono text-xs font-bold text-amber-300">MVP MAIN QUEST</div>
              <h4 className="font-bold text-amber-200">主线任务提示</h4>
            </div>
            <p className="leading-7 text-slate-300">
              我已经准备好一条适合计算机系同学演示的职业规划主线：选择职业、生成任务、查资料、提交评审、进入作品集。
            </p>
            <PixelButton variant="primary" onClick={onScrollToTasks} fullWidth>
              查看主管任务
            </PixelButton>
          </div>
        </PixelCard>
      ) : null}

      <div className="border-4 border-slate-700 bg-slate-900 p-4">
        <div className="mb-4 flex items-center gap-3">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden border-2 border-amber-600 bg-slate-950">
            <Image src={config.image} alt={config.name} fill sizes="64px" className="object-cover" />
            <div className="absolute inset-0 bg-slate-950/15" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="pixel-title text-lg font-bold text-amber-300">{config.name}</h3>
            <p className="mb-2 text-sm text-slate-400">{config.title}</p>
            <div className="flex flex-wrap gap-2">
              <PixelBadge variant="success" className="text-xs">
                {config.status}
              </PixelBadge>
              <PixelBadge variant="neutral" className="text-xs">
                {config.mode}
              </PixelBadge>
            </div>
          </div>
        </div>
        <div className="border-2 border-slate-700 bg-slate-950 p-3">
          <p className="text-sm italic leading-7 text-slate-300">"{config.prompt}"</p>
        </div>
      </div>

      <AgentThinkingPanel careerId={careerId} />

      <AgentMissionFeed resources={resources} careerId={careerId} onOpenRAGDrawer={onOpenRAGDrawer} />

      <FeynmanChallengeCard careerId={careerId} missionId={missionId} />

      <div className="border-4 border-slate-700 bg-slate-900/80 p-3">
        <h4 className="mb-2 text-xs font-bold text-slate-400">快捷行动</h4>
        <div className="grid grid-cols-2 gap-2">
          <PixelButton variant="secondary" className="py-2 text-xs">
            继续任务
          </PixelButton>
          <PixelButton variant="secondary" className="py-2 text-xs">
            查看反馈
          </PixelButton>
          <PixelButton variant="secondary" className="py-2 text-xs" onClick={onOpenResourceDialog}>
            推荐资源
          </PixelButton>
          <PixelButton variant="primary" className="py-2 text-xs" onClick={onOpenRAGDrawer}>
            RAG 检索
          </PixelButton>
        </div>
      </div>
    </div>
  );
}
