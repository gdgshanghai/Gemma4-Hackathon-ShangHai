'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Image from 'next/image';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { AgentChat } from '@/components/agent';
import { ErrorState, LoadingState } from '@/components/common';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelCard, PixelDialog } from '@/components/pixel';
import SubmissionChecklist from '@/components/mission/SubmissionChecklist';
import SubmissionEditor from '@/components/mission/SubmissionEditor';
import SubmissionHistoryPanel from '@/components/mission/SubmissionHistoryPanel';
import SubmissionQualityPanel from '@/components/mission/SubmissionQualityPanel';
import { ROUTES } from '@/constants';
import { getCareerImage, getMentorImage, IMAGES } from '@/constants/images';
import { missionService } from '@/services';
import { useMissionStore } from '@/stores/missionStore';
import { Mission, MissionStatus } from '@/types';
import { getCareerRouteByMissionId } from '@/utils';
import { MVP_MOCK_REPORT } from '@/utils/demoFlow';

interface ValidationErrors {
  report?: string;
}

export default function MissionSubmitPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const missionId = params.missionId as string;
  const isDemoMode = searchParams.get('demo') === '1';

  const { getDraft, saveDraft, submitMission, completeMission, getMissionStatus } = useMissionStore();

  const [report, setReport] = useState('');
  const [code, setCode] = useState('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saved, setSaved] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mission, setMission] = useState<Mission | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>({});
  const [showMentorDialog, setShowMentorDialog] = useState(false);

  const loadMission = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const missionData = await missionService.getMissionById(missionId);
      if (!missionData) {
        setError('没有找到这张任务卡。');
        return;
      }
      setMission(missionData);
    } catch (err) {
      setError('任务信息加载失败，请稍后重试。');
      console.error('Failed to load mission:', err);
    } finally {
      setLoading(false);
    }
  }, [missionId]);

  useEffect(() => {
    loadMission();
    const draft = getDraft(missionId);
    if (draft) {
      setReport(draft.report);
      setCode(draft.code);
    }
  }, [missionId, getDraft, loadMission]);

  const currentMissionStatus = mission ? getMissionStatus(missionId, mission.status) : MissionStatus.LOCKED;
  const isLocked = currentMissionStatus === MissionStatus.LOCKED;
  const isCompleted = currentMissionStatus === MissionStatus.COMPLETED;

  const validateForm = useCallback((): boolean => {
    const errors: ValidationErrors = {};
    const trimmedReport = report.trim();
    if (!trimmedReport) {
      errors.report = '请先写下任务报告。';
    } else if (trimmedReport.length < 30) {
      errors.report = '报告至少需要 30 个字，让导师能看懂你的思路。';
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [report]);

  const getCurrentQualityScore = useCallback(() => {
    if (typeof window === 'undefined') return 0;
    const savedChecklist = localStorage.getItem(`careercraft-submission-checklist-${missionId}`);
    if (!savedChecklist) return 0;
    try {
      return Object.values(JSON.parse(savedChecklist)).filter(Boolean).length;
    } catch {
      return 0;
    }
  }, [missionId]);

  const saveSubmissionHistory = useCallback(() => {
    const storageKey = `careercraft-submission-history-${missionId}`;
    const history = localStorage.getItem(storageKey);
    const historyArray = history ? JSON.parse(history) : [];
    historyArray.unshift({
      missionId,
      submittedAt: new Date().toISOString(),
      reportLength: report.trim().length,
      qualityScore: getCurrentQualityScore(),
      status: 'submitted',
    });
    localStorage.setItem(storageKey, JSON.stringify(historyArray));
  }, [getCurrentQualityScore, missionId, report]);

  const handleSaveDraft = useCallback(() => {
    saveDraft(missionId, { report, code });
    setSaved(true);
    setHasUnsavedChanges(false);
    window.setTimeout(() => setSaved(false), 1800);
  }, [missionId, report, code, saveDraft]);

  const handleSubmit = useCallback(async () => {
    if (!validateForm()) return;

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      saveDraft(missionId, { report, code });
      saveSubmissionHistory();
      const result = await missionService.evaluateSubmission(
        missionId,
        [report.trim(), code.trim() ? `\n\n附加材料：\n${code.trim()}` : ''].join(''),
      );
      if (result.mission_status === 'completed' || !result.trigger_feynman_challenge) {
        completeMission(missionId);
      } else {
        submitMission(missionId);
      }
      router.push(ROUTES.MISSION_FEEDBACK(missionId) + (isDemoMode ? '?demo=1&step=7' : ''));
    } catch (err) {
      console.error('Failed to submit mission:', err);
      setSubmitError('提交评审失败，结果未保存到后端。请确认任务仍处于进行中并稍后重试。');
      setIsSubmitting(false);
    }
  }, [code, completeMission, isDemoMode, missionId, report, router, saveDraft, saveSubmissionHistory, submitMission, validateForm]);

  const isSubmitDisabled = isSubmitting || !report.trim() || report.trim().length < 30 || isLocked || isCompleted;
  const careerId = mission?.careerId || 'data-analyst';
  const backgroundImage = mission ? getCareerImage(careerId) : IMAGES.MISSION_WORKBENCH;
  const backRoute = mission ? getCareerRouteByMissionId(missionId) : ROUTES.LOBBY;

  if (loading) {
    return (
      <AppShell>
        <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH} position="center center">
          <LoadingState message="正在打开实训提交台..." />
        </ScenePage>
      </AppShell>
    );
  }

  if (error || !mission) {
    return (
      <AppShell>
        <ScenePage backgroundImage={IMAGES.MISSION_WORKBENCH} position="center center">
          <ErrorState title="任务加载失败" message={error || '没有找到这张任务卡。'} onRetry={loadMission} />
        </ScenePage>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <ScenePage backgroundImage={backgroundImage} maxWidth="7xl" position="center center">
        <div className="space-y-8 py-8">
          <section className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
            <div className="border-4 border-slate-700 bg-slate-950/75 p-6">
              <div className="mb-4 flex flex-wrap gap-2">
                <PixelBadge variant="warning">任务提交</PixelBadge>
                <PixelBadge variant="neutral">计算机系职业模拟</PixelBadge>
              </div>
              <h1 className="pixel-title text-3xl text-amber-300 md:text-4xl">把这次实训交给导师</h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200">
                你提交的不是标准答案，而是一份能被 AI 同事复盘、能沉淀进作品集的职业草图。
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <PixelButton variant="secondary" onClick={() => router.push(`${ROUTES.MISSION(missionId)}${isDemoMode ? '?demo=1&step=5' : ''}`)}>
                  返回任务台
                </PixelButton>
                <PixelButton variant="secondary" onClick={handleSaveDraft} disabled={isSubmitting}>
                  保存草稿
                </PixelButton>
                {isDemoMode ? (
                  <PixelButton
                    variant="secondary"
                    onClick={() => {
                      setReport(MVP_MOCK_REPORT);
                      setHasUnsavedChanges(true);
                    }}
                  >
                    填入演示报告
                  </PixelButton>
                ) : null}
              </div>
            </div>

            <PixelCard className="bg-slate-950/75">
              <div className="flex items-start gap-4">
                <div className="relative h-20 w-20 shrink-0 overflow-hidden border-4 border-amber-500 bg-slate-900">
                  <Image src={getMentorImage(careerId)} alt="导师头像" fill className="object-cover" sizes="80px" />
                </div>
                <div>
                  <p className="pixel-title text-lg text-amber-300">导师提示</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    先说明你如何理解任务，再说明你如何做。职业探索最重要的是把思路说清楚。
                  </p>
                </div>
              </div>
            </PixelCard>
          </section>

          {saved ? <div className="border-2 border-emerald-500 bg-emerald-950/40 p-3 text-sm font-bold text-emerald-200">草稿已保存。</div> : null}
          {validationErrors.report ? <div className="border-2 border-red-500 bg-red-950/40 p-3 text-sm font-bold text-red-100">{validationErrors.report}</div> : null}
          {submitError ? <div className="border-2 border-red-500 bg-red-950/40 p-3 text-sm font-bold text-red-100">{submitError}</div> : null}

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-5">
              <SubmissionEditor
                report={report}
                code={code}
                onReportChange={(value) => {
                  setReport(value);
                  setHasUnsavedChanges(true);
                }}
                onCodeChange={(value) => {
                  setCode(value);
                  setHasUnsavedChanges(true);
                }}
                hasUnsavedChanges={hasUnsavedChanges}
              />

              <div className="flex flex-wrap items-center gap-3">
                {isCompleted ? (
                  <PixelButton onClick={() => router.push(ROUTES.MISSION_FEEDBACK(missionId))}>查看评审反馈</PixelButton>
                ) : isLocked ? (
                  <PixelButton disabled>任务尚未解锁</PixelButton>
                ) : (
                  <PixelButton onClick={handleSubmit} disabled={isSubmitDisabled}>
                    {isSubmitting ? '提交中...' : '提交给 AI 导师评审'}
                  </PixelButton>
                )}
                <PixelButton variant="secondary" onClick={() => router.push(`/feynman/${missionId}${isDemoMode ? '?demo=1&step=4' : ''}`)}>
                  先做费曼挑战
                </PixelButton>
              </div>
            </div>

            <aside className="space-y-5">
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
                    {careerId === 'data-analyst' ? 'DA' : careerId === 'software-engineer' ? 'SE' : careerId === 'product-designer' ? 'PD' : 'AI'}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="pixel-title text-lg text-amber-300">
                      {careerId === 'data-analyst' ? '林澈' : careerId === 'software-engineer' ? '陈明' : careerId === 'product-designer' ? '周婷' : '杨帆'}
                    </h3>
                    <p className="mt-1 text-sm text-slate-300">
                      {careerId === 'data-analyst' ? '数据山脉导师' : careerId === 'software-engineer' ? '硅之岛导师' : careerId === 'product-designer' ? '产品设计港导师' : 'AI实验室导师'}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">点击开始对话</p>
                  </div>
                </div>
              </div>
              <PixelCard title="任务摘要">
                <div className="space-y-3">
                  <h2 className="font-bold text-slate-100">{mission.title}</h2>
                  <p className="text-sm leading-6 text-slate-300">{mission.background}</p>
                  <div className="flex flex-wrap gap-2">
                    <PixelBadge variant={mission.difficulty === 'hard' ? 'danger' : 'warning'}>
                      {mission.difficulty === 'easy' ? '入门' : mission.difficulty === 'medium' ? '进阶' : '挑战'}
                    </PixelBadge>
                    <PixelBadge variant="success">+{mission.rewardExp} XP</PixelBadge>
                  </div>
                  {mission.mockDataUrl ? (
                    <PixelButton
                      variant="secondary"
                      className="mt-3"
                      onClick={() => window.open(mission.mockDataUrl, '_blank', 'noopener,noreferrer')}
                    >
                      下载任务数据集
                    </PixelButton>
                  ) : null}
                </div>
              </PixelCard>
              <SubmissionChecklist missionId={missionId} />
              <SubmissionQualityPanel report={report} />
              <SubmissionHistoryPanel missionId={missionId} />
            </aside>
          </div>

          <PixelDialog
            open={showMentorDialog}
            onClose={() => setShowMentorDialog(false)}
            title="导师对话"
            size="lg"
          >
            <AgentChat
              careerId={careerId}
              stage="submit"
              missionTitle={mission.title}
              compact
            />
          </PixelDialog>
        </div>
      </ScenePage>
    </AppShell>
  );
}
