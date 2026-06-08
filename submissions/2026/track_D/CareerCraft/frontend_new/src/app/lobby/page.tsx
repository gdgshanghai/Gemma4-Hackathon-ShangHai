'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton } from '@/components/pixel';
import CareerPreviewPanel from '@/components/lobby/CareerPreviewPanel';
import CareerWorldMap, { CareerMapIsland } from '@/components/lobby/CareerWorldMap';
import DemoGuideBar from '@/components/demo/DemoGuideBar';
import MvpFlowPanel from '@/components/demo/MvpFlowPanel';
import WorldMapLegend from '@/components/lobby/WorldMapLegend';
import { IMAGES } from '@/constants/images';
import { careerService } from '@/services';

type ApiStatus = 'connected' | 'fallback' | 'error';

function LobbyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemoMode = searchParams.get('demo') === '1';
  const [selectedIsland, setSelectedIsland] = useState<CareerMapIsland | null>(null);
  const [careerOverrides, setCareerOverrides] = useState<
    { id: string; name: string; description: string; unlocked: boolean }[]
  >([]);
  const [careerApiStatus, setCareerApiStatus] = useState<ApiStatus>('fallback');

  useEffect(() => {
    let alive = true;
    careerService
      .getAllCareerIslandsWithSource()
      .then(({ data, source }) => {
        if (!alive) return;
        setCareerOverrides(
          data.map((item) => ({
            id: item.id,
            name: item.name,
            description: item.description,
            unlocked: item.unlocked,
          })),
        );
        setCareerApiStatus(source === 'api' ? 'connected' : 'fallback');
      })
      .catch(() => {
        if (!alive) return;
        setCareerOverrides([]);
        setCareerApiStatus('error');
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.CAREER_CAMPUS_BACKDROP} maxWidth="7xl" position="center center">
        <div className="space-y-6 py-8">
          {isDemoMode ? (
            <DemoGuideBar
              currentStep={7}
              nextStepTitle="重新体验 MVP 演示"
              nextStepAction="/career/data-analyst?demo=1"
            />
          ) : null}

          <section className="border-4 border-slate-700 bg-slate-950/82 p-6 text-center backdrop-blur-sm">
            <PixelBadge variant="warning">职业大陆地图</PixelBadge>
            <h1 className="pixel-title mt-4 text-3xl text-amber-300 md:text-5xl">选择你的第一条职业路线</h1>
            <p className="mx-auto mt-4 max-w-3xl text-sm leading-7 text-slate-300">
              这是一张给计算机系大学生准备的职业规划草图。先在大陆上观察不同职业岛，
              再选择一条路线进入真实任务模拟。
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <PixelButton onClick={() => router.push('/career/data-analyst?demo=1')}>
                开始 MVP 演示
              </PixelButton>
              <PixelButton variant="secondary" onClick={() => router.push('/portfolio')}>
                查看成长档案馆
              </PixelButton>
            </div>
          </section>

          <MvpFlowPanel />

          <div className="flex justify-end">
            <PixelBadge variant={careerApiStatus === 'connected' ? 'success' : careerApiStatus === 'error' ? 'danger' : 'warning'}>
              {careerApiStatus === 'connected'
                ? 'Careers API connected'
                : careerApiStatus === 'error'
                  ? 'Careers API error'
                  : 'Careers fallback data'}
            </PixelBadge>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-2">
              <div className="border-4 border-slate-700 bg-slate-950/84 p-4 backdrop-blur-sm">
                <CareerWorldMap onIslandSelect={setSelectedIsland} careerOverrides={careerOverrides} />
              </div>
              <WorldMapLegend />

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <PixelButton onClick={() => router.push('/career/data-analyst')} className="w-full">
                  数据山脉
                </PixelButton>
                <PixelButton variant="secondary" onClick={() => router.push('/career/software-engineer')} className="w-full">
                  硅之岛
                </PixelButton>
                <PixelButton variant="secondary" onClick={() => router.push('/career/product-designer')} className="w-full">
                  产品设计港
                </PixelButton>
                <PixelButton variant="ghost" onClick={() => router.push('/')} className="w-full">
                  返回首页
                </PixelButton>
              </div>
            </div>

            <aside className="lg:sticky lg:top-4 lg:self-start">
              <CareerPreviewPanel career={selectedIsland} />
            </aside>
          </div>

          <p className="text-center text-sm text-slate-500">
            点击职业岛查看预览。可进入的岛屿会带你进入任务、费曼挑战、提交评审和作品集沉淀流程。
          </p>
        </div>
      </ScenePage>
    </AppShell>
  );
}

function LobbyFallback() {
  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.CAREER_CAMPUS_BACKDROP} position="center center">
        <div className="flex min-h-[60vh] items-center justify-center text-center">
          <div>
            <span className="pixel-blink text-3xl">...</span>
            <p className="mt-2 text-slate-400">正在加载职业大陆...</p>
          </div>
        </div>
      </ScenePage>
    </AppShell>
  );
}

export default function LobbyPage() {
  return (
    <Suspense fallback={<LobbyFallback />}>
      <LobbyContent />
    </Suspense>
  );
}
