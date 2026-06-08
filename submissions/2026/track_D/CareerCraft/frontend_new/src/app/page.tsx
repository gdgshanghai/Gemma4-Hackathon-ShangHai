'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AgentChat } from '@/components/agent';
import { ErrorState, LoadingState } from '@/components/common';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelCard, PixelProgress } from '@/components/pixel';
import { getCareerImage, IMAGES } from '@/constants/images';
import { ROUTES } from '@/constants';
import { useCareer } from '@/hooks';

export default function HomePage() {
  const router = useRouter();
  const { careers, activeCareer, currentCareerId, totalXp, loading, error, refresh } = useCareer();
  const [selectedCareer, setSelectedCareer] = useState(careers[0] || null);

  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.CAREER_CAMPUS_BACKDROP} maxWidth="7xl" position="center center">
        <section className="grid gap-6 py-8 lg:grid-cols-[minmax(0,1.45fr)_420px]">
          <div className="space-y-6">
            <div className="border-4 border-slate-700 bg-slate-950/84 p-6 backdrop-blur-sm">
              <PixelBadge variant="warning">Career Continent Online</PixelBadge>
              <h1 className="pixel-title mt-5 text-4xl leading-tight text-amber-300 md:text-6xl">
                CareerCraft
              </h1>
              <p className="mt-5 max-w-3xl text-sm leading-7 text-amber-100/80">
                面向计算机系大学生的 AI 职业模拟沙盒。进入职业大陆，完成真实岗位任务，
                接受 AI 同事评审，再把能力证据沉淀成作品集。
              </p>

              <div className="mt-6 flex flex-wrap gap-3">
                <PixelButton onClick={() => router.push('/lobby')}>探索职业大陆</PixelButton>
                {currentCareerId ? (
                  <PixelButton variant="secondary" onClick={() => router.push(ROUTES.CAREER(currentCareerId))}>
                    进入当前职业岛
                  </PixelButton>
                ) : null}
                <PixelButton variant="ghost" onClick={() => router.push('/portfolio')}>
                  查看成长档案馆
                </PixelButton>
              </div>
            </div>

            <PixelCard className="border-slate-700 bg-slate-950/84 p-5 backdrop-blur-sm">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="pixel-title text-xl text-amber-300">职业岛屿</h2>
                  <p className="mt-2 text-xs leading-5 text-slate-400">
                    优先连接真实导师网络；网络不畅时自动切换本地知识库，保证职业体验不断线。
                  </p>
                </div>
                <PixelButton variant="secondary" onClick={() => refresh()}>
                  刷新
                </PixelButton>
              </div>

              {loading ? (
                <LoadingState message="正在同步职业大陆..." />
              ) : error ? (
                <ErrorState
                  title="职业数据同步失败"
                  message="导师网络暂时不可用。点击重试会再次连接导师网络，失败时仍保留本地学习体验。"
                  onRetry={() => refresh().catch(() => undefined)}
                />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {careers.map((career) => (
                    <button
                      key={career.id}
                      onClick={() => setSelectedCareer(career)}
                      className="group text-left"
                    >
                      <div
                        className={`h-full overflow-hidden border-2 bg-slate-950/70 transition group-hover:-translate-y-0.5 ${
                          career.id === selectedCareer?.id
                            ? 'border-amber-500'
                            : career.id === currentCareerId
                            ? 'border-emerald-500'
                            : 'border-slate-700 group-hover:border-amber-700'
                        }`}
                      >
                        <div
                          className="h-28 border-b border-slate-700"
                          style={{
                            backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.72), rgba(2,6,23,0.20)), url(${getCareerImage(career.id)})`,
                            backgroundSize: 'cover',
                            backgroundPosition: 'center',
                          }}
                        />
                        <div className="p-4">
                          <div className="flex items-center justify-between gap-2">
                            <h3 className="font-bold text-white">{career.name}</h3>
                            {career.id === currentCareerId ? <PixelBadge variant="success">当前</PixelBadge> : null}
                            {career.id === selectedCareer?.id && career.id !== currentCareerId ? (
                              <PixelBadge variant="warning">已选</PixelBadge>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-amber-200/70">{career.islandName}</p>
                          <p className="mt-3 line-clamp-3 text-xs leading-5 text-slate-400">
                            {career.description}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </PixelCard>

            <div className="grid gap-4 md:grid-cols-3">
              {[
                ['真实任务', '生成职业场景任务，完成后进入 AI 评审。'],
                ['RAG 支援', '卡住时检索知识库，获得教程和示例。'],
                ['费曼挑战', '用自己的话解释概念，验证是否真正理解。'],
              ].map(([title, desc]) => (
                <div key={title} className="border-2 border-slate-700 bg-slate-950/78 p-4 backdrop-blur-sm">
                  <h3 className="font-bold text-amber-200">{title}</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-400">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          <aside className="space-y-5 lg:sticky lg:top-4 lg:self-start">
            {selectedCareer ? (
              <PixelCard className="border-amber-700 bg-slate-950/84 p-5 backdrop-blur-sm">
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs text-slate-400">选中职业</p>
                      <h2 className="mt-2 text-xl font-bold text-amber-300">
                        {selectedCareer.name}
                      </h2>
                      <p className="mt-1 text-xs text-slate-400">
                        {selectedCareer.islandName}
                      </p>
                    </div>
                    <div className="flex h-12 w-12 items-center justify-center border-2 border-amber-500 font-bold text-amber-300">
                      {selectedCareer.id === 'software-engineer'
                        ? 'SE'
                        : selectedCareer.id === 'product-designer'
                          ? 'PD'
                          : selectedCareer.id === 'ai-researcher'
                            ? 'AI'
                            : 'DA'}
                    </div>
                  </div>

                  <div
                    className="h-24 border-2 border-slate-700"
                    style={{
                      backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.72), rgba(2,6,23,0.20)), url(${getCareerImage(selectedCareer.id)})`,
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                    }}
                  />

                  <div className="space-y-2">
                    <div>
                      <p className="text-xs text-slate-500">导师</p>
                      <p className="text-sm text-slate-300">{selectedCareer.mentorName}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">职业简介</p>
                      <p className="line-clamp-3 text-sm leading-6 text-slate-300">{selectedCareer.description}</p>
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-xs text-slate-500">可探索岗位</p>
                    <div className="flex flex-wrap gap-1">
                      {selectedCareer.careers.slice(0, 3).map((career) => (
                        <PixelBadge key={career.id} variant="neutral" className="text-xs">
                          {career.name}
                        </PixelBadge>
                      ))}
                    </div>
                  </div>

                  <PixelButton fullWidth onClick={() => router.push(ROUTES.CAREER(selectedCareer.id))}>
                    进入职业岛
                  </PixelButton>
                </div>
              </PixelCard>
            ) : (
              <PixelCard className="border-amber-700 bg-slate-950/84 p-5 backdrop-blur-sm">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs text-slate-400">当前进度</p>
                    <h2 className="mt-2 text-xl font-bold text-white">
                      {activeCareer?.name ?? '尚未选择职业'}
                    </h2>
                    <p className="mt-1 text-xs text-slate-400">
                      {activeCareer
                        ? `${activeCareer.islandName} / ${activeCareer.mentorName}`
                        : '先选择一个职业岛'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-amber-300">{totalXp}</p>
                    <p className="text-xs text-slate-500">XP</p>
                  </div>
                </div>
                <div className="mt-5">
                  <PixelProgress value={Math.min(totalXp / 10, 100)} label="职业成长" color="#f59e0b" />
                </div>
              </PixelCard>
            )}

            <div className="h-[520px] overflow-hidden border-2 border-slate-700 bg-slate-950/88 backdrop-blur-sm">
              <AgentChat
                careerId={selectedCareer?.id || currentCareerId || activeCareer?.id || 'data-analyst'}
                stage="home"
                pageTopic="职业大陆入口"
                agentName={selectedCareer?.mentorName || activeCareer?.mentorName}
                agentAvatar={selectedCareer?.mentorAvatar || activeCareer?.mentorAvatar}
                agentRole={selectedCareer ? `${selectedCareer.name}导师` : activeCareer ? `${activeCareer.name}导师` : '职业导航导师'}
              />
            </div>
          </aside>
        </section>
      </ScenePage>
    </AppShell>
  );
}
