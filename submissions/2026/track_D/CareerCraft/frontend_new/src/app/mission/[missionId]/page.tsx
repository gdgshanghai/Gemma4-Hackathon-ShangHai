'use client';

import React from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { AgentChat } from '@/components/agent';
import DemoGuideBar from '@/components/demo/DemoGuideBar';
import DemoHighlight from '@/components/demo/DemoHighlight';
import {
  MissionBriefScroll,
  MissionClientRequest,
  MissionDeliverableBoard,
  MissionMentorHint,
  MissionQuestHeader,
  MissionStartPanel,
} from '@/components/mission';
import { ErrorState, LoadingState } from '@/components/common';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelCard, PixelDialog } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { getCareerImage, IMAGES } from '@/constants/images';
import { careerService, missionService } from '@/services';
import { Mission } from '@/types';
import { getDemoStep, isDemoMode, MVP_MISSION_ID } from '@/utils/demoFlow';

export default function MissionWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const missionId = params.missionId as string;
  const isDemo = isDemoMode(searchParams);
  const currentStep = getDemoStep(searchParams);
  const isMvpMission = missionId === MVP_MISSION_ID;

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [mission, setMission] = React.useState<Mission | null>(null);
  const [careerName, setCareerName] = React.useState('数据山脉');
  const [showMentorDialog, setShowMentorDialog] = React.useState(false);

  React.useEffect(() => {
    let alive = true;

    async function loadMission() {
      setLoading(true);
      setError(null);
      try {
        const missionData = await missionService.getMissionById(missionId);
        if (!alive) return;

        if (!missionData) {
          setError('没有找到这张任务卡。');
          return;
        }

        setMission(missionData);
        const career = await careerService.getCareerIslandById(missionData.careerId || '');
        if (alive) {
          setCareerName(career?.name || '职业岛');
        }
      } catch (err) {
        if (alive) {
          setError('任务加载失败，请稍后重试。');
          console.error('Failed to load mission:', err);
        }
      } finally {
        if (alive) setLoading(false);
      }
    }

    loadMission();
    return () => {
      alive = false;
    };
  }, [missionId]);

  const backRoute = mission?.careerId ? `${ROUTES.CAREER(mission.careerId)}${isDemo ? '?demo=1&step=1' : ''}` : ROUTES.LOBBY;

  if (loading) {
    return (
      <AppShell>
        <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH}>
          <LoadingState message="正在打开任务工作台..." />
        </ScenePage>
      </AppShell>
    );
  }

  if (error || !mission) {
    return (
      <AppShell>
        <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH}>
          <ErrorState title="任务加载失败" message={error || '没有找到这张任务卡，请回到职业大厅重新选择。'} onRetry={() => router.push(backRoute)} />
        </ScenePage>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH} maxWidth="7xl" position="center center">
        <div className="space-y-8 py-8">
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="border-4 border-slate-700 bg-slate-950/80 p-6 backdrop-blur-sm">
              <div className="mb-4 flex flex-wrap gap-2">
                <PixelBadge variant="warning">任务工作台</PixelBadge>
                <PixelBadge variant="neutral">{careerName}</PixelBadge>
              </div>
              <h1 className="pixel-title text-3xl text-amber-300 md:text-4xl">阅读需求，拆解交付</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200">
                这里模拟一次真实项目的开工会议。先读懂背景，再把需求拆成可交付行动，最后决定是否接受任务并进入提交阶段。
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <PixelButton variant="secondary" onClick={() => router.push(backRoute)}>
                  返回职业岛
                </PixelButton>
                <PixelButton variant="secondary" onClick={() => router.push(`/feynman/${mission.id}${isDemo ? '?demo=1&step=4' : ''}`)}>
                  去挑战室预习
                </PixelButton>
                {mission.mockDataUrl ? (
                  <PixelButton variant="secondary" onClick={() => window.open(mission.mockDataUrl, '_blank', 'noopener,noreferrer')}>
                    下载任务数据集
                  </PixelButton>
                ) : null}
              </div>
            </div>

            <RewardPanel mission={mission} />
          </section>

          {isDemo && isMvpMission ? (
            <>
              {currentStep === 2 ? (
                <DemoGuideBar currentStep={2} nextStepTitle="寻找学习资源" nextStepAction={`/mission/${MVP_MISSION_ID}?demo=1&step=3`} />
              ) : null}
              {currentStep === 3 ? (
                <DemoGuideBar currentStep={3} nextStepTitle="完成费曼挑战" nextStepAction={`/feynman/${MVP_MISSION_ID}?demo=1&step=4`} />
              ) : null}
              {currentStep === 5 ? (
                <DemoGuideBar currentStep={5} nextStepTitle="提交分析报告" nextStepAction={`/mission/${MVP_MISSION_ID}/submit?demo=1&step=6`} />
              ) : null}
            </>
          ) : null}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="space-y-5 lg:col-span-8">
              <DemoHighlight targetStep={2} currentStep={currentStep} label="任务详细信息">
                <MissionQuestHeader mission={mission} careerName={careerName} />
              </DemoHighlight>

              <DemoHighlight targetStep={2} currentStep={currentStep}>
                <MissionBriefScroll mission={mission} />
              </DemoHighlight>

              <MissionClientRequest mission={mission} />
              <MissionDeliverableBoard />
            </div>

            <aside className="space-y-5 lg:col-span-4">
              <div
                className="border-2 border-slate-700 bg-slate-950/84 cursor-pointer p-4 transition-colors hover:border-amber-500"
                onClick={() => setShowMentorDialog(true)}
                style={{
                  backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.8), rgba(2,6,23,0.4)), url(${getCareerImage(mission.careerId || 'data-analyst')})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                }}
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center border-2 border-amber-500 font-bold text-amber-300">
                    {(mission.careerId || 'data-analyst') === 'data-analyst' ? 'DA' : (mission.careerId || 'software-engineer') === 'software-engineer' ? 'SE' : (mission.careerId || 'product-designer') === 'product-designer' ? 'PD' : 'AI'}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="pixel-title text-lg text-amber-300">
                      {(mission.careerId || 'data-analyst') === 'data-analyst' ? '林澈' : (mission.careerId || 'software-engineer') === 'software-engineer' ? '陈明' : (mission.careerId || 'product-designer') === 'product-designer' ? '周婷' : '杨帆'}
                    </h3>
                    <p className="mt-1 text-sm text-slate-300">
                      {(mission.careerId || 'data-analyst') === 'data-analyst' ? '数据山脉导师' : (mission.careerId || 'software-engineer') === 'software-engineer' ? '硅之岛导师' : (mission.careerId || 'product-designer') === 'product-designer' ? '产品设计港导师' : 'AI实验室导师'}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">点击开始对话</p>
                  </div>
                </div>
              </div>
              <MissionMentorHint careerId={mission.careerId || ''} />
              <PixelCard title="故事位置" className="bg-slate-950/85">
                <p className="text-sm leading-6 text-slate-300">
                  你现在处在“任务完成阶段”：接受委托、完成交付、提交评审，然后把反馈转化为技能成长。
                </p>
              </PixelCard>
              <DemoHighlight targetStep={5} currentStep={currentStep} label="接受 AI 主管任务">
                <MissionStartPanel mission={mission} />
              </DemoHighlight>
            </aside>
          </div>

          <PixelDialog
            open={showMentorDialog}
            onClose={() => setShowMentorDialog(false)}
            title="导师对话"
            size="lg"
          >
            <AgentChat
              careerId={mission.careerId || 'data-analyst'}
              stage="mission"
              missionTitle={mission.title}
              compact
            />
          </PixelDialog>
        </div>
      </ScenePage>
    </AppShell>
  );
}

function RewardPanel({ mission }: { mission: Mission }) {
  return (
    <PixelCard className="border-slate-700 bg-slate-950/85 p-5 backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-bold text-amber-300">任务奖励</h2>
        <PixelBadge variant="warning">+{mission.rewardExp} XP</PixelBadge>
      </div>
      <div className="space-y-3">
        <RewardRow label="成长经验" value={`+${mission.rewardExp} XP`} />
        <RewardRow label="作品集证据" value="可沉淀" />
        <RewardRow label="技能成长" value={mission.rewardSkills.length > 0 ? `${mission.rewardSkills.length} 项` : '待解锁'} />
      </div>
    </PixelCard>
  );
}

function RewardRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-2 border-slate-700 bg-slate-900/60 p-3 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="font-bold text-slate-100">{value}</span>
    </div>
  );
}
