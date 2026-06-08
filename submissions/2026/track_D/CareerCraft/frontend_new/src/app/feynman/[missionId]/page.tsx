'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { AgentChat } from '@/components/agent';
import { BackButton } from '@/components/common';
import DemoGuideBar from '@/components/demo/DemoGuideBar';
import DemoHighlight from '@/components/demo/DemoHighlight';
import FeynmanAnswerBox from '@/components/feynman/FeynmanAnswerBox';
import FeynmanFeedbackPanel from '@/components/feynman/FeynmanFeedbackPanel';
import FeynmanHeader from '@/components/feynman/FeynmanHeader';
import FeynmanQuestionCard from '@/components/feynman/FeynmanQuestionCard';
import FeynmanRubric from '@/components/feynman/FeynmanRubric';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelCard, PixelDialog } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { getCareerImage, IMAGES } from '@/constants/images';
import { feedbackService } from '@/services/feedbackService';
import { useMissionStore } from '@/stores/missionStore';
import { getDemoStep, isDemoMode, MVP_MISSION_ID } from '@/utils/demoFlow';

const questionBank = {
  'software-engineer': [
    { id: 'se-1', text: '为什么修 Bug 前要先复现问题？', type: 'why', difficulty: 'easy' as const },
    { id: 'se-2', text: '什么是最小复现？它为什么能节省排查时间？', type: 'definition', difficulty: 'medium' as const },
  ],
  'data-analyst': [
    { id: 'da-1', text: '请用最简单的话解释：什么是用户活跃度？', type: 'definition', difficulty: 'easy' as const },
    { id: 'da-2', text: '为什么不能只看 DAU 就判断产品是否健康？', type: 'why', difficulty: 'medium' as const },
  ],
  'product-designer': [
    { id: 'pm-1', text: '为什么产品第一版不能把所有功能都做进去？', type: 'why', difficulty: 'easy' as const },
    { id: 'pm-2', text: '什么是用户旅程？它如何帮助团队发现真正的问题？', type: 'definition', difficulty: 'medium' as const },
  ],
  'ai-researcher': [
    { id: 'ai-1', text: '为什么 AI 实验必须先写清假设？', type: 'why', difficulty: 'easy' as const },
    { id: 'ai-2', text: '什么是失败样本？它为什么比只看平均分更有价值？', type: 'definition', difficulty: 'medium' as const },
  ],
};

const generateRubric = () => [
  { name: '说得简单', icon: 'A', score: 22, maxScore: 25 },
  { name: '有类比', icon: 'B', score: 21, maxScore: 25 },
  { name: '能举例', icon: 'C', score: 20, maxScore: 25 },
  { name: '少术语', icon: 'D', score: 22, maxScore: 25 },
];

export default function FeynmanChallengePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const missionId = params.missionId as string;
  const isDemo = isDemoMode(searchParams);
  const currentStep = getDemoStep(searchParams);
  const isMvpMission = missionId === MVP_MISSION_ID;
  const { completeMission } = useMissionStore();

  const [step, setStep] = useState<'question' | 'feedback'>('question');
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState<any>(null);
  const [rubric, setRubric] = useState<any>(null);
  const [careerType, setCareerType] = useState<keyof typeof questionBank>('software-engineer');
  const [backendQuestion, setBackendQuestion] = useState<string | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showMentorDialog, setShowMentorDialog] = useState(false);

  useEffect(() => {
    if (missionId.includes('data') || missionId.includes('activity') || missionId.includes('community')) {
      setCareerType('data-analyst');
    } else if (missionId.startsWith('pm-')) {
      setCareerType('product-designer');
    } else if (missionId.startsWith('ai-')) {
      setCareerType('ai-researcher');
    }
  }, [missionId]);

  useEffect(() => {
    if (isDemo) {
      setBackendQuestion(null);
      setQuestionError(null);
      return;
    }

    let alive = true;
    setQuestionLoading(true);
    setQuestionError(null);

    feedbackService.getFeynmanChallenge(missionId)
      .then((challenge) => {
        if (!alive) return;
        if (challenge.careerId in questionBank) {
          setCareerType(challenge.careerId as keyof typeof questionBank);
        }
        if (challenge.active && challenge.question) {
          setBackendQuestion(challenge.question);
        } else {
          setBackendQuestion(null);
          setQuestionError('当前任务还没有后端激活的费曼挑战。请先提交任务并完成 AI 评审。');
        }
      })
      .catch(() => {
        if (!alive) return;
        setBackendQuestion(null);
        setQuestionError('无法读取后端费曼挑战，当前答案不会保存。请稍后重试。');
      })
      .finally(() => {
        if (alive) setQuestionLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [isDemo, missionId]);

  const questions = questionBank[careerType];
  const currentQuestion = !isDemo && backendQuestion
    ? { id: `backend-${missionId}`, text: backendQuestion, type: 'why', difficulty: 'medium' as const }
    : isDemo
      ? questions[0]
      : questions[currentQuestionIndex];
  const canAnswer = isDemo || Boolean(backendQuestion);

  const handleSubmit = async () => {
    if (answer.length < 30 || isSubmitting) return;
    if (!canAnswer) {
      setSubmitError('当前没有可保存到后端的费曼挑战。');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    const newRubric = generateRubric();
    const totalScore = newRubric.reduce((sum, item) => sum + item.score, 0);
    setRubric(newRubric);

    if (isDemo) {
      setFeedback({
        score: totalScore,
        maxScore: 100,
        rating: totalScore >= 85 ? '理解深入' : '理解良好',
        aiFeedback: '演示反馈：解释方向清楚，能把概念和当前任务联系起来。',
        strengths: ['解释清晰', '能联系任务场景'],
        improvements: ['可以补充一个更生活化的例子'],
        badgeEarned: totalScore >= 70,
      });
      setIsSubmitting(false);
      setStep('feedback');
      return;
    }

    try {
      const result = await feedbackService.submitFeynmanAnswer(missionId, answer);
      setFeedback({
        score: totalScore,
        maxScore: 100,
        rating: totalScore >= 85 ? '理解深入' : '理解良好',
        aiFeedback: result.feedback,
        strengths: ['解释清晰', '能联系任务场景'],
        improvements: ['可以补充一个更生活化的例子'],
        badgeEarned: totalScore >= 70,
        ...result,
      });
      if (result.mission_status === 'completed') {
        completeMission(missionId);
      }
      setStep('feedback');
    } catch {
      setSubmitError('费曼挑战提交失败，答案未保存到后端。请稍后重试。');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetry = () => {
    setAnswer('');
    setStep('question');
    setFeedback(null);
    setRubric(null);
    setSubmitError(null);
    if (!isDemo) {
      setCurrentQuestionIndex((prev) => (prev + 1) % questions.length);
    }
  };

  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.FEYNMAN_CHAMBER} maxWidth="7xl" position="center center">
        <div className="space-y-6 py-8">
          <BackButton
            fallbackHref={`${ROUTES.MISSION(missionId)}${isDemo ? '?demo=1&step=3' : ''}`}
            label="返回任务卡"
          />

          {isDemo && isMvpMission && currentStep === 4 ? (
            <>
              <DemoGuideBar
                currentStep={4}
                nextStepTitle="接受 AI 主管任务"
                nextStepAction={`/mission/${MVP_MISSION_ID}?demo=1&step=5`}
              />
              <PixelCard className="border-amber-700 bg-amber-950/30 p-4">
                <p className="text-sm leading-6 text-amber-100">
                  演示模式使用本地费曼题，不会写入后端。
                </p>
              </PixelCard>
            </>
          ) : null}

          <DemoHighlight targetStep={4} currentStep={currentStep} label="回答费曼问题">
            <div className="space-y-5">
              <FeynmanHeader missionId={missionId} />

              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
                <div className="space-y-5">
                  <section className="grid gap-4 md:grid-cols-3">
                    <StoryHint title="第一步" text="先说人话：它到底是什么。" />
                    <StoryHint title="第二步" text="再接任务：它在当前项目里解决什么问题。" />
                    <StoryHint title="第三步" text="最后举例：像给同学讲一样。" />
                  </section>

                  {step === 'question' ? (
                    <>
                      {questionLoading ? (
                        <PixelCard>
                          <p className="text-sm text-slate-300">正在读取后端费曼挑战...</p>
                        </PixelCard>
                      ) : !canAnswer ? (
                        <PixelCard className="border-red-700 bg-red-950/30">
                          <PixelBadge variant="danger">未激活</PixelBadge>
                          <p className="mt-3 text-sm leading-6 text-red-100">{questionError}</p>
                          <PixelButton
                            className="mt-4"
                            variant="secondary"
                            onClick={() => router.push(ROUTES.MISSION_SUBMIT(missionId))}
                          >
                            去提交任务
                          </PixelButton>
                        </PixelCard>
                      ) : (
                        <>
                          <FeynmanQuestionCard
                            question={currentQuestion}
                            questionNumber={isDemo ? 1 : currentQuestionIndex + 1}
                            totalQuestions={isDemo ? 1 : questions.length}
                          />
                          {submitError ? (
                            <div className="border-2 border-red-500 bg-red-950/40 p-3 text-sm font-bold text-red-100">
                              {submitError}
                            </div>
                          ) : null}
                          <FeynmanAnswerBox value={answer} onChange={setAnswer} onSubmit={handleSubmit} disabled={isSubmitting} />
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      <FeynmanRubric rubrics={rubric} />
                      <FeynmanFeedbackPanel
                        feedback={feedback}
                        onBackToMission={() => router.push(ROUTES.MISSION(missionId) + (isDemo ? '?demo=1&step=5' : ''))}
                        onBackToSubmit={() => router.push(ROUTES.MISSION_SUBMIT(missionId) + (isDemo ? '?demo=1&step=6' : ''))}
                        onRetry={handleRetry}
                      />
                    </>
                  )}
                </div>

                <aside className="lg:sticky lg:top-6 lg:self-start">
                  <div
                    className="cursor-pointer border-2 border-slate-700 bg-slate-950/84 p-4 transition-colors hover:border-amber-500"
                    onClick={() => setShowMentorDialog(true)}
                    style={{
                      backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.8), rgba(2,6,23,0.4)), url(${getCareerImage(careerType)})`,
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                    }}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-14 w-14 items-center justify-center border-2 border-amber-500 font-bold text-amber-300">
                        {careerType === 'data-analyst' ? 'DA' : careerType === 'software-engineer' ? 'SE' : careerType === 'product-designer' ? 'PD' : 'AI'}
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="pixel-title text-lg text-amber-300">导师对话</h3>
                        <p className="mt-1 text-sm text-slate-300">点击开始对话</p>
                      </div>
                    </div>
                  </div>
                </aside>
              </div>
            </div>
          </DemoHighlight>

          <PixelDialog
            open={showMentorDialog}
            onClose={() => setShowMentorDialog(false)}
            title="导师对话"
            size="lg"
          >
            <AgentChat
              careerId={careerType}
              stage="feynman"
              missionTitle={missionId}
              pageTopic="费曼挑战"
              compact
            />
          </PixelDialog>
        </div>
      </ScenePage>
    </AppShell>
  );
}

function StoryHint({ title, text }: { title: string; text: string }) {
  return (
    <div className="border-2 border-slate-700 bg-slate-950/75 p-4">
      <PixelBadge variant="neutral">{title}</PixelBadge>
      <p className="mt-3 text-sm leading-6 text-slate-300">{text}</p>
    </div>
  );
}
