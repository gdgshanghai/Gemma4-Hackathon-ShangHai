'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import {
  CareerAtmospherePanel,
  CareerDashboard,
  CareerIslandHero,
  CareerPathRoadmap,
  CareerProgressBanner,
  CareerQuickActions,
  CareerResourcePanel,
  CareerSkillTree,
  CareerTaskBoard,
} from '@/components/career';
import { FloatingMentor } from '@/components/agent';
import { EngineerMailboxDialog } from '@/components/community';
import { ErrorState, LoadingState } from '@/components/common';
import DemoGuideBar from '@/components/demo/DemoGuideBar';
import DemoHighlight from '@/components/demo/DemoHighlight';
import { AppShell, PageContainer, ScenePage } from '@/components/layout';
import { ROUTES } from '@/constants';
import { getCareerImage } from '@/constants/images';
import { MentorMood } from '@/data';
import { MVP_MISSION } from '@/data/mvpMission';
import { careerService, missionService, resourceService, skillService } from '@/services';
import { useMissionStore } from '@/stores/missionStore';
import { useUserStore } from '@/stores/userStore';
import { CareerIsland, Mission, Resource, SkillNode } from '@/types';
import { getDemoStep, isDemoMode, MVP_MISSION_ID } from '@/utils/demoFlow';

export default function CareerHubPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const careerId = params.careerId as string;
  const isDemo = isDemoMode(searchParams);
  const currentStep = getDemoStep(searchParams);
  const isDataAnalyst = careerId === 'data-analyst';
  const { resetMissionStatuses } = useMissionStore();
  const { selectCareer } = useUserStore();

  const taskBoardRef = useRef<HTMLDivElement>(null);
  const skillTreeRef = useRef<HTMLDivElement>(null);

  const [careerInfo, setCareerInfo] = useState<CareerIsland | undefined>();
  const [skills, setSkills] = useState<SkillNode[]>([]);
  const [missionData, setMissionData] = useState<Mission[]>([]);
  const [resourceData, setResourceData] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [mentorCue, setMentorCue] = useState('');
  const [mentorMood, setMentorMood] = useState<MentorMood>('idle');
  const [mentorOpen, setMentorOpen] = useState(false);
  const [mailboxOpen, setMailboxOpen] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      if (isDemo && isDataAnalyst) {
        resetMissionStatuses();
      }

      const [career, loadedSkills, loadedMissions, loadedResources] = await Promise.all([
        careerService.getCareerIslandById(careerId),
        skillService.getSkillsByCareerId(careerId),
        missionService.getMissionsByCareerId(careerId),
        resourceService.getResourcesByCareerId(careerId),
      ]);
      if (!career) {
        setLoading(false);
        return;
      }

      const missionList =
        isDemo && isDataAnalyst
          ? [MVP_MISSION, ...loadedMissions.filter((mission) => mission.id !== MVP_MISSION.id)]
          : loadedMissions;

      setCareerInfo(career);
      setSkills(loadedSkills);
      setMissionData(missionList);
      setResourceData(loadedResources);
    } catch (err) {
      console.error('Error loading data:', err);
    } finally {
      setLoading(false);
    }
  }, [careerId, isDataAnalyst, isDemo, resetMissionStatuses]);

  const handleScrollToTasks = () => {
    taskBoardRef.current?.scrollIntoView({ behavior: 'smooth' });
    setMentorCue('我看到你打开任务板了。先选一张能沉淀作品集的主线任务。');
    setMentorMood('encouraging');
  };

  const handleScrollToSkills = () => {
    skillTreeRef.current?.scrollIntoView({ behavior: 'smooth' });
    setMentorCue('技能树不是装饰，先点亮和当前任务相关的能力。');
    setMentorMood('thinking');
  };

  const handleAskMentor = () => {
    setMentorCue('这个问题如果涉及环境、排查顺序或人工经验，就写进工程师信箱。把背景和尝试过的办法写清楚。');
    setMentorMood('warning');
    setMailboxOpen(true);
  };

  const handleMissionGenerated = useCallback((mission: Mission, source: 'api' | 'fallback') => {
    setMissionData((current) => {
      const withoutDuplicate = current.filter((item) => item.id !== mission.id);
      return [{ ...mission, careerId }, ...withoutDuplicate];
    });
    setMentorCue(
      source === 'api'
        ? '新任务已从后端 API 生成，并加入当前训练计划。'
        : '后端暂不可用，已加入离线模拟任务；这条记录不会保存到后端。',
    );
    setMentorMood(source === 'api' ? 'encouraging' : 'warning');
  }, [careerId]);

  const handleDemoNext = () => {
    if (currentStep === 1) {
      router.push(`/mission/${MVP_MISSION_ID}?demo=1&step=2`);
    }
  };

  useEffect(() => {
    let alive = true;
    selectCareer(careerId)
      .catch((error) => {
        console.warn('Career selection sync failed before loading career page.', error);
      })
      .finally(() => {
        if (alive) {
          loadData();
        }
      });
    return () => {
      alive = false;
    };
  }, [careerId, loadData, selectCareer]);

  if (loading) {
    return (
      <AppShell>
        <ScenePage backgroundImage={getCareerImage(careerId)} position="center center">
          <LoadingState message="正在进入职业岛..." />
        </ScenePage>
      </AppShell>
    );
  }

  if (!careerInfo) {
    return (
      <AppShell>
        <ScenePage backgroundImage={getCareerImage(careerId)} position="center center">
          <ErrorState
            title="职业岛不存在"
            message={`未找到 ID 为 ${careerId} 的职业岛。`}
            onRetry={() => router.push(ROUTES.LOBBY)}
          />
        </ScenePage>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div
        className="relative min-h-screen"
        style={{
          backgroundImage: `linear-gradient(180deg, rgba(2,6,23,0.82) 0%, rgba(2,6,23,0.66) 34%, rgba(2,6,23,0.92) 100%), url(${getCareerImage(careerId)})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center top',
          backgroundAttachment: 'fixed',
        }}
      >
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[length:100%_5px] opacity-40" />

        <PageContainer maxWidth="6xl">
          <div className="relative z-10 space-y-6 py-8">
            {isDemo && isDataAnalyst ? (
              <>
                {currentStep === 1 ? (
                  <DemoGuideBar currentStep={1} nextStepTitle="查看主管任务" nextStepAction={handleDemoNext} />
                ) : null}
                {currentStep === 2 ? (
                  <DemoGuideBar
                    currentStep={2}
                    nextStepTitle="查看任务详情"
                    nextStepAction={`/mission/${MVP_MISSION_ID}?demo=1&step=2`}
                  />
                ) : null}
              </>
            ) : null}

            <DemoHighlight targetStep={1} currentStep={currentStep} label="进入职业岛主线">
              <CareerIslandHero careerId={careerId} careerName={careerInfo.name} />
            </DemoHighlight>

            <CareerProgressBanner
              currentStage="校园传送门"
              nextStage="岗位能力试炼"
              currentGoal="完成 1 个真实任务，获得 AI 同事评审"
              progress={35}
            />

            <CareerQuickActions
              onScrollToTasks={handleScrollToTasks}
              onScrollToSkills={handleScrollToSkills}
              onAskMentor={handleAskMentor}
            />

            <CareerDashboard missions={missionData} skills={skills} />

            <div ref={taskBoardRef} id="career-task-board">
              <DemoHighlight targetStep={2} currentStep={currentStep} label="查看 AI 主管推荐的任务">
                <CareerTaskBoard
                  missions={missionData}
                  careerId={careerId}
                  isDemoMode={isDemo}
                  onMissionGenerated={handleMissionGenerated}
                />
              </DemoHighlight>
            </div>

            <CareerResourcePanel
              resources={resourceData}
              careerId={careerId}
              missions={missionData}
              isDemoMode={isDemo}
              onScrollToTasks={handleScrollToTasks}
            />

            <div ref={skillTreeRef}>
              <CareerSkillTree skills={skills} />
            </div>

            <CareerPathRoadmap careerId={careerId} missions={missionData} />
            <CareerAtmospherePanel careerId={careerId} />
          </div>
        </PageContainer>
        <FloatingMentor
          careerId={careerId}
          stage="career"
          pageTopic={`${careerInfo.name}职业岛`}
          cue={mentorCue}
          mood={mentorMood}
          open={mentorOpen}
          onOpenChange={setMentorOpen}
        />
        <EngineerMailboxDialog open={mailboxOpen} onClose={() => setMailboxOpen(false)} careerId={careerId} />
      </div>
    </AppShell>
  );
}
