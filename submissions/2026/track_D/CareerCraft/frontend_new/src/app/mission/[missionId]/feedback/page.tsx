'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { AgentChat } from '@/components/agent';
import DemoGuideBar from '@/components/demo/DemoGuideBar';
import { ErrorState, LoadingState } from '@/components/common';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelCard, PixelDialog, PixelProgress } from '@/components/pixel';
import { getCareerImage, IMAGES } from '@/constants/images';
import { ROUTES } from '@/constants';
import { feedbackService, missionService } from '@/services';
import { useMissionStore } from '@/stores/missionStore';
import { Feedback, Mission, MissionStatus } from '@/types';
import { getDemoStep, isDemoMode, MVP_MISSION_ID } from '@/utils/demoFlow';

interface FeedbackViewModel {
  totalScore: number;
  grade: string;
  mentorComment: string;
  dimensions: Array<{ name: string; score: number; maxScore: number; color: string }>;
  highlights: string[];
  suggestions: string[];
  expGained: Array<{ name: string; xp: number; progress: number }>;
  badge: string;
}

function buildFeedbackViewModel(feedback: Feedback | undefined, isDemo: boolean, isMvpMission: boolean): FeedbackViewModel {
  if (feedback) {
    return {
      totalScore: feedback.score,
      grade: feedback.score >= 90 ? 'S' : feedback.score >= 82 ? 'A' : 'B+',
      mentorComment: feedback.comment,
      dimensions: [
        { name: '任务完成度', score: 22, maxScore: 25, color: '#10b981' },
        { name: '证据链', score: 20, maxScore: 25, color: '#38bdf8' },
        { name: '表达清晰度', score: 18, maxScore: 25, color: '#f59e0b' },
        { name: '业务理解', score: 22, maxScore: 25, color: '#818cf8' },
      ],
      highlights: feedback.strengths,
      suggestions: feedback.improvements,
      expGained: (feedback.skillExpGained || []).map((item) => ({ name: item.skillId, xp: item.expGained, progress: 75 })),
      badge: feedback.badgesEarned?.[0] || '数据侦察员',
    };
  }

  if (isDemo && isMvpMission) {
    return {
      totalScore: 82,
      grade: 'A',
      mentorComment:
        '你能从活跃下降的问题里拆出时间趋势、用户分层和行为路径，这已经很接近真实数据分析师的工作方式。下一步可以把建议写得更具体，比如先做哪类访谈、看哪组指标。',
      dimensions: [
        { name: '问题拆解', score: 23, maxScore: 25, color: '#10b981' },
        { name: '数据口径', score: 21, maxScore: 25, color: '#38bdf8' },
        { name: '可视化表达', score: 19, maxScore: 25, color: '#f59e0b' },
        { name: '建议可行性', score: 19, maxScore: 25, color: '#818cf8' },
      ],
      highlights: ['抓住了核心指标变化', '能按用户分层拆解问题', '报告结构清楚，适合放入作品集'],
      suggestions: ['补充一个具体图表或指标口径', '把建议拆成优先级', '说明如何验证建议是否有效'],
      expGained: [
        { name: '问题拆解', xp: 10, progress: 84 },
        { name: '数据口径', xp: 8, progress: 76 },
        { name: '业务表达', xp: 6, progress: 72 },
      ],
      badge: '数据侦察员',
    };
  }

  return {
    totalScore: 82,
    grade: 'A',
    mentorComment: '这份交付物已经能说明你理解了任务背景，也能表达解决过程。下一次可以继续补充证据、边界条件和更具体的行动计划。',
    dimensions: [
      { name: '任务完成度', score: 22, maxScore: 25, color: '#10b981' },
      { name: '专业准确度', score: 20, maxScore: 25, color: '#38bdf8' },
      { name: '表达清晰度', score: 18, maxScore: 25, color: '#f59e0b' },
      { name: '职业理解', score: 22, maxScore: 25, color: '#818cf8' },
    ],
    highlights: ['理解了任务目标', '交付物结构完整', '能说明关键思路'],
    suggestions: ['补充更多证据或示例', '结论部分可以更具体', '增加后续验证方式'],
    expGained: [
      { name: '问题拆解', xp: 10, progress: 80 },
      { name: '表达复盘', xp: 8, progress: 75 },
      { name: '职业理解', xp: 6, progress: 70 },
    ],
    badge: '职业探索者',
  };
}

export default function MissionFeedbackPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const missionId = params.missionId as string;
  const isDemo = isDemoMode(searchParams);
  const currentStep = getDemoStep(searchParams);
  const isMvpMission = missionId === MVP_MISSION_ID;

  const [mission, setMission] = useState<Mission | undefined>();
  const [feedback, setFeedback] = useState<Feedback | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMentorDialog, setShowMentorDialog] = useState(false);
  const { completeMission } = useMissionStore();

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [missionData, feedbackData] = await Promise.all([
        missionService.getMissionById(missionId),
        feedbackService.getFeedbackByMissionId(missionId),
      ]);
      if (!missionData) {
        setError('没有找到这张任务卡。');
        return;
      }
      setMission(missionData);
      setFeedback(feedbackData);
      if (!feedbackData && !(isDemo && isMvpMission)) {
        setError('没有找到真实评审结果。请先提交任务并等待后端评审完成。');
        return;
      }
      if (missionData.status === MissionStatus.COMPLETED) {
        completeMission(missionId);
      }
    } catch (err) {
      setError('评审结果加载失败，请稍后重试。');
      console.error('Failed to load feedback:', err);
    } finally {
      setLoading(false);
    }
  }, [completeMission, isDemo, isMvpMission, missionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const feedbackData = useMemo(() => buildFeedbackViewModel(feedback, isDemo, isMvpMission), [feedback, isDemo, isMvpMission]);

  if (loading) {
    return (
      <AppShell>
        <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH} position="center center">
          <LoadingState message="导师正在整理评审报告..." />
        </ScenePage>
      </AppShell>
    );
  }

  if (error || !mission) {
    return (
      <AppShell>
        <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH} position="center center">
          <ErrorState title="评审加载失败" message={error || '没有找到评审数据。'} onRetry={loadData} />
        </ScenePage>
      </AppShell>
    );
  }

  const careerId = mission.careerId || 'data-analyst';
  const totalXP = feedbackData.expGained.reduce((sum, item) => sum + item.xp, 0);

  return (
    <AppShell>
      <ScenePage backgroundImage={getCareerImage(careerId)} maxWidth="7xl" position="center center">
        <div className="space-y-8 py-8">
          {isDemo && isMvpMission && currentStep === 7 ? (
            <DemoGuideBar currentStep={7} nextStepTitle="沉淀作品集" nextStepAction={`${ROUTES.PORTFOLIO}?demo=1&step=8`} />
          ) : null}

          <section
            className="border-4 border-slate-700 bg-slate-950/80 p-6 backdrop-blur-sm"
            style={{
              backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.9), rgba(2,6,23,0.7)), url(${getCareerImage(careerId)})`,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
            }}
          >
            <div className="mb-4 flex flex-wrap gap-2">
              <PixelBadge variant="success">任务完成</PixelBadge>
              <PixelBadge variant="warning">导师评审报告</PixelBadge>
            </div>
            <h1 className="pixel-title text-3xl text-amber-300 md:text-4xl">评审室回执</h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200">
              这一页把一次任务变成职业成长记录：AI 同事拆解交付物，导师给出建议，最后沉淀到技能树和作品集里。
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <PixelButton variant="secondary" onClick={() => router.push(`${ROUTES.CAREER(careerId)}${isDemo ? '?demo=1&step=1' : ''}`)}>
                回到职业岛
              </PixelButton>
              <PixelButton variant="secondary" onClick={() => router.push(`${ROUTES.PORTFOLIO}${isDemo ? '?demo=1&step=8' : ''}`)}>
                查看作品集
              </PixelButton>
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-4">
              <PixelCard title="综合评分">
                <div className="text-center">
                  <div className="text-6xl font-black text-amber-300">{feedbackData.totalScore}</div>
                  <div className="mt-2 text-sm text-slate-400">等级 {feedbackData.grade}</div>
                  <div className="mt-4">
                    <PixelProgress value={feedbackData.totalScore} color="#f59e0b" />
                  </div>
                </div>
              </PixelCard>

              <PixelCard title="成长奖励">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-slate-400">获得徽章</span>
                  <PixelBadge variant="honor">{feedbackData.badge}</PixelBadge>
                </div>
                <div className="mb-4 text-sm font-bold text-emerald-300">+{totalXP} XP</div>
                <div className="space-y-3">
                  {feedbackData.expGained.map((item) => (
                    <div key={item.name}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="text-slate-300">{item.name}</span>
                        <span className="text-amber-300">+{item.xp}</span>
                      </div>
                      <PixelProgress value={item.progress} height="h-4" />
                    </div>
                  ))}
                </div>
              </PixelCard>
            </div>

            <div className="space-y-6 lg:col-span-5">
              <PixelCard title="维度拆解">
                <div className="space-y-4">
                  {feedbackData.dimensions.map((dimension) => (
                    <div key={dimension.name}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="text-slate-300">{dimension.name}</span>
                        <span className="text-amber-300">
                          {dimension.score}/{dimension.maxScore}
                        </span>
                      </div>
                      <PixelProgress value={(dimension.score / dimension.maxScore) * 100} color={dimension.color} height="h-4" />
                    </div>
                  ))}
                </div>
              </PixelCard>

              <PixelCard title="导师评语">
                <p className="leading-7 text-slate-300">{feedbackData.mentorComment}</p>
              </PixelCard>
            </div>

            <div className="space-y-6 lg:col-span-3">
              <div
                className="border-2 border-slate-700 bg-slate-950/84 cursor-pointer p-4 transition-colors hover:border-amber-500"
                onClick={() => setShowMentorDialog(true)}
                style={{
                  backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.8), rgba(2,6,23,0.4)), url(${getCareerImage(careerId)})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                }}
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center border-2 border-amber-500 font-bold text-amber-300">
                    DA
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="pixel-title text-lg text-amber-300">林澈</h3>
                    <p className="mt-1 text-sm text-slate-300">数据山脉导师</p>
                    <p className="mt-1 text-xs text-slate-400">点击开始对话</p>
                  </div>
                </div>
              </div>
              <FeedbackList title="亮点" items={feedbackData.highlights} marker="OK" />
              <FeedbackList title="下一步建议" items={feedbackData.suggestions} marker="UP" />
              <PixelCard title="本次任务">
                <h2 className="mb-3 font-bold text-slate-100">{mission.title}</h2>
                <p className="text-sm leading-6 text-slate-300">{mission.description}</p>
              </PixelCard>
            </div>
          </div>
        </div>

        <PixelDialog
          open={showMentorDialog}
          onClose={() => setShowMentorDialog(false)}
          title="导师对话"
          size="lg"
        >
          <AgentChat
            careerId={careerId}
            stage="feedback"
            missionTitle={mission.title}
            compact
          />
        </PixelDialog>
      </ScenePage>
    </AppShell>
  );
}

function FeedbackList({ title, items, marker }: { title: string; items: string[]; marker: string }) {
  return (
    <PixelCard title={title}>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2 text-sm leading-6 text-slate-300">
            <span className="font-mono text-amber-400">{marker}</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </PixelCard>
  );
}
