'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { EngineerMailboxDialog } from '@/components/community';
import RAGSearchDrawer from '@/components/resource/RAGSearchDrawer';
import ResourceRecommendDialog from '@/components/resource/ResourceRecommendDialog';
import { PixelBadge, PixelButton } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { getMentorImage } from '@/constants/images';
import { Mission, Resource } from '@/types';

interface CareerResourcePanelProps {
  resources: Resource[];
  careerId: string;
  missions: Mission[];
  missionId?: string;
  isDemoMode?: boolean;
  onScrollToTasks?: () => void;
}

export default function CareerResourcePanel({
  resources,
  careerId,
  missions,
  missionId,
  isDemoMode,
  onScrollToTasks,
}: CareerResourcePanelProps) {
  const router = useRouter();
  const [showResourceDialog, setShowResourceDialog] = useState(false);
  const [showMailboxDialog, setShowMailboxDialog] = useState(false);
  const [showRAGDrawer, setShowRAGDrawer] = useState(false);
  const mentorImage = getMentorImage(careerId);
  const featuredResources = resources.slice(0, 3);

  return (
    <>
      <section className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-center gap-4">
            <img src={mentorImage} alt="AI mentor portrait" className="h-16 w-16 border-2 border-amber-600 object-cover" />
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.16em] text-emerald-300">Human Support</div>
              <h2 className="mt-1 text-lg font-bold text-amber-300">工程师信箱</h2>
              <PixelBadge variant="success" className="mt-2 text-xs">社区开放</PixelBadge>
            </div>
          </div>
          <p className="mb-4 text-sm leading-6 text-slate-400">
            AI 适合拆思路；真实工程经验适合处理环境、边界、协作和排查细节。把卡住的问题发布到社区，让人来帮你判断。
          </p>
          <div className="grid gap-2">
            <PixelButton onClick={() => setShowMailboxDialog(true)} fullWidth>写一封工程师信</PixelButton>
            <PixelButton variant="secondary" onClick={() => router.push(`${ROUTES.COMMUNITY}?career=${careerId}`)} fullWidth>
              进入交流社区
            </PixelButton>
            <PixelButton variant="ghost" onClick={onScrollToTasks} fullWidth>回到任务委托</PixelButton>
          </div>
        </div>

        <div className="border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
                Knowledge Archive
              </div>
              <h2 className="pixel-title text-2xl font-bold text-amber-300">知识档案库</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                把学习资料接到当前职业委托上。需要的时候检索，不让页面变成资料堆。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <PixelButton variant="secondary" onClick={() => setShowResourceDialog(true)}>推荐资源</PixelButton>
              <PixelButton onClick={() => setShowRAGDrawer(true)}>RAG 检索</PixelButton>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {(featuredResources.length > 0 ? featuredResources : fallbackResources).map((resource) => (
              <article key={resource.id} className="border border-slate-700 bg-slate-900/58 p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <PixelBadge variant="neutral" className="text-xs">{resource.type}</PixelBadge>
                  {typeof resource.relevance === 'number' ? (
                    <span className="font-mono text-xs text-emerald-300">{resource.relevance}%</span>
                  ) : null}
                </div>
                <h3 className="mb-2 line-clamp-2 font-bold leading-5 text-amber-200">{resource.title}</h3>
                <p className="line-clamp-3 text-xs leading-5 text-slate-400">
                  {resource.summary ?? '与当前职业试炼相关的学习资料。'}
                </p>
              </article>
            ))}
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <ArchiveBadge title="任务上下文" value={`${missions.length} 项`} />
            <ArchiveBadge title="当前模式" value={isDemoMode ? '演示主线' : '自由探索'} />
            <ArchiveBadge title="绑定任务" value={missionId ? '已绑定' : '职业岛'} />
          </div>
        </div>
      </section>

      <ResourceRecommendDialog open={showResourceDialog} onClose={() => setShowResourceDialog(false)} />
      <EngineerMailboxDialog open={showMailboxDialog} onClose={() => setShowMailboxDialog(false)} careerId={careerId} />
      <RAGSearchDrawer open={showRAGDrawer} onClose={() => setShowRAGDrawer(false)} taskType={careerId as any} />
    </>
  );
}

function ArchiveBadge({ title, value }: { title: string; value: string }) {
  return (
    <div className="border border-slate-700 bg-slate-900/52 p-3">
      <div className="font-mono text-xs uppercase tracking-[0.16em] text-slate-500">{title}</div>
      <div className="mt-1 font-bold text-amber-200">{value}</div>
    </div>
  );
}

const fallbackResources: Resource[] = [
  {
    id: 'fallback-sql',
    title: '职业任务入门路线',
    type: '课程',
    summary: '从背景理解、任务拆解、交付表达三个步骤进入真实职业模拟。',
    relevance: 92,
  },
  {
    id: 'fallback-dashboard',
    title: '项目复盘示例',
    type: '案例',
    summary: '学习如何把一次任务整理成能放进作品集的成长证据。',
    relevance: 88,
  },
  {
    id: 'fallback-portfolio',
    title: '作品集表达模板',
    type: '模板',
    summary: '把任务背景、分析过程、结论和下一步建议整理成可展示成果。',
    relevance: 84,
  },
];
