'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AgentChat } from '@/components/agent';
import DemoGuideBar from '@/components/demo/DemoGuideBar';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelCard, PixelProgress } from '@/components/pixel';
import { careerService, missionService, skillService } from '@/services';
import { useUserStore } from '@/stores/userStore';
import { IMAGES } from '@/constants/images';
import { isDemoMode } from '@/utils/demoFlow';

const milestones = [
  { id: 'm1', name: '新手起航', subtitle: '完成任意一个职业岛任务', achieved: true, xpAwarded: 20 },
  { id: 'm2', name: '快速交付', subtitle: '完成一次高质量任务提交', achieved: true, xpAwarded: 30 },
  { id: 'm3', name: '费曼挑战者', subtitle: '用自己的话讲清一个核心概念', achieved: true, xpAwarded: 40 },
  { id: 'm4', name: 'AI 同事认可', subtitle: '在导师评审中获得明确亮点', achieved: true, xpAwarded: 50 },
  { id: 'm5', name: '第一份作品', subtitle: '将任务报告沉淀进作品集', achieved: true, xpAwarded: 30 },
];

export default function PortfolioPage() {
  return (
    <Suspense fallback={null}>
      <PortfolioContent />
    </Suspense>
  );
}

function PortfolioContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemo = isDemoMode(searchParams);
  const [careerId, setCareerId] = useState('data-analyst');
  const [completedMissions, setCompletedMissions] = useState(1);
  const [totalXp, setTotalXp] = useState(380);
  const [skillCount, setSkillCount] = useState(5);
  const [loading, setLoading] = useState(true);
  const { currentCareerId, totalXp: storeXp } = useUserStore();

  useEffect(() => {
    let alive = true;

    async function fetchPortfolioData() {
      try {
        const careers = await careerService.getAllCareerIslands();
        const activeCareerId = currentCareerId || (careers.length > 0 ? careers[0].id : 'data-analyst');
        const [skills, missions] = await Promise.all([
          skillService.getSkillsByCareerId(activeCareerId),
          missionService.getMissions(),
        ]);

        if (!alive) return;
        setCareerId(activeCareerId);
        setTotalXp(storeXp || 380);
        setSkillCount(skills.length > 0 ? skills.filter((skill) => skill.level > 0 || skill.unlocked).length : 5);
        setCompletedMissions(Math.max(1, missions.filter((mission) => mission.status === 'completed').length));
      } catch {
        if (!alive) return;
        setTotalXp(380);
        setSkillCount(5);
        setCompletedMissions(1);
        setCareerId('data-analyst');
      } finally {
        if (alive) setLoading(false);
      }
    }

    fetchPortfolioData();
    return () => {
      alive = false;
    };
  }, [currentCareerId, storeXp]);

  const achievedMilestones = milestones.filter((milestone) => milestone.achieved).length;
  const progress = Math.round((achievedMilestones / milestones.length) * 100);

  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.PORTFOLIO_ARCHIVE} maxWidth="7xl" position="center center">
        <div className="space-y-8 py-8">
          {isDemo ? <DemoGuideBar currentStep={8} nextStepTitle="重新体验 MVP 演示" nextStepAction="/career/data-analyst?demo=1&step=1" /> : null}

          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="border-4 border-slate-700 bg-slate-950/80 p-6 backdrop-blur-sm">
              <PixelBadge variant="warning">作品档案馆</PixelBadge>
              <h1 className="pixel-title mt-4 text-3xl text-amber-300 md:text-5xl">成长档案馆</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200">
                这里记录的不是简历终点，而是一张逐渐清晰的职业规划草图。每一次任务、费曼挑战和 AI 评审，都会变成你能讲清楚的成长证据。
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <PixelButton onClick={() => router.push(careerId ? `/career/${careerId}` : '/lobby')}>回到职业岛</PixelButton>
                <PixelButton variant="secondary" onClick={() => router.push('/lobby')}>探索其他路线</PixelButton>
              </div>
            </div>

            <AgentChat
              careerId={careerId}
              stage="portfolio"
              pageTopic="成长档案馆"
              compact
              className="min-h-[360px]"
            />

            <PixelCard className="hidden bg-slate-950/80">
              <p className="pixel-title text-lg text-amber-300">档案说明</p>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                对计算机系学生来说，职业规划不该只停留在“想做什么”。它应该能回答：我做过什么任务、学会什么技能、下一步该补什么能力。
              </p>
            </PixelCard>
          </section>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
            <StatCard label="总经验值" value={loading ? '...' : `${totalXp} XP`} />
            <StatCard label="完成任务" value={loading ? '...' : completedMissions} />
            <StatCard label="技能节点" value={loading ? '...' : skillCount} />
            <StatCard label="里程碑" value={loading ? '...' : `${achievedMilestones}/${milestones.length}`} />
          </div>

          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <PixelCard className="border-slate-700 bg-slate-950/85 p-5 backdrop-blur-sm">
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <h2 className="pixel-title text-xl text-amber-300">里程碑证据墙</h2>
                  <p className="mt-2 text-sm text-slate-400">每个节点都对应一个可以在面试或作品集中讲清楚的成长证据。</p>
                </div>
                <PixelBadge variant="warning">{progress}%</PixelBadge>
              </div>

              <div className="mb-5">
                <PixelProgress value={progress} color="#f59e0b" />
              </div>

              <div className="divide-y divide-slate-800">
                {milestones.map((milestone) => (
                  <div key={milestone.id} className="flex items-center gap-4 py-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-emerald-500 bg-emerald-500/20 text-sm font-bold text-emerald-200">
                      ✓
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-bold text-white">{milestone.name}</p>
                      <p className="text-sm text-slate-400">{milestone.subtitle}</p>
                    </div>
                    <div className="text-sm font-bold text-emerald-400">+{milestone.xpAwarded} XP</div>
                  </div>
                ))}
              </div>
            </PixelCard>

            <aside className="space-y-4">
              <ArchiveTip title="作品集提示">
                一份好的职业作品集不只展示结果，也展示你如何理解问题、选择方法、验证结论。
              </ArchiveTip>
              <ArchiveTip title="下一步建议">
                回到职业岛领取下一张任务卡，把刚得到的技能节点继续补进档案。
              </ArchiveTip>
              <ArchiveTip title="面试表达练习">
                试着用“背景、行动、结果、反思”四句话讲清一项任务，这会让作品集更有故事。
              </ArchiveTip>
            </aside>
          </section>
        </div>
      </ScenePage>
    </AppShell>
  );
}

function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border-4 border-slate-700 bg-slate-950/80 p-4 backdrop-blur-sm">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-bold text-amber-300">{value}</p>
    </div>
  );
}

function ArchiveTip({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <PixelCard className="bg-slate-950/85">
      <h3 className="font-bold text-amber-300">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-slate-400">{children}</p>
    </PixelCard>
  );
}
